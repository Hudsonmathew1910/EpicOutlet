import json
import logging
import queue
import threading
from functools import partial, wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Case, Count, F, Q, Sum, When
from django.db.models.functions import TruncDate
from django.db import close_old_connections, connection
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from api.chat_service import chat_with_ai
from . import payments, search as catalog_search, services
from .form import CheckoutForm, CustomUserForm, ProfileForm, ReviewForm
from .models import Catagory, Order, Product, ProductReview, cart, fav, get_ava_url
from .ratelimit import client_key, hit, rate_limit

logger = logging.getLogger(__name__)

PRODUCTS_PER_PAGE = 12
SORTS = {
    'popular': ('-Trending', '-rating_count', '-Created_at'),
    'low_high': ('selling_price',),
    'high_low': ('-selling_price',),
    'discount': ('-discount',),
    'rating': ('-avg_rating', '-rating_count'),
    'newest': ('-Created_at',),
    'vendor': ('vendor',),
}
SORT_LABELS = [
    ('popular', 'Popularity'), ('low_high', 'Price: Low to High'), ('high_low', 'Price: High to Low'),
    ('discount', 'Discount'), ('rating', 'Customer Rating'), ('newest', 'Newest First'),
]
PRICE_BUCKETS = [(0, 999), (1000, 4999), (5000, 14999), (15000, 29999), (30000, None)]


def _json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return {}


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ajax_login_required(view):
    """Like login_required, but answers JSON so fetch() callers can prompt a login."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'Login to continue', 'login_url': reverse('login')}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


def _filter_products(request, products):
    """Apply the shared filter/sort query params. Returns (queryset, active filters)."""
    f = {
        'category': request.GET.get('category', '').strip(),
        'vendor': request.GET.get('vendor', '').strip(),
        'min_price': _int(request.GET.get('min_price')),
        'max_price': _int(request.GET.get('max_price')),
        'trending': request.GET.get('trending') == '1',
        'in_stock': request.GET.get('in_stock') == '1',
        'sort': request.GET.get('sort', '') if request.GET.get('sort') in SORTS else '',
        'search': request.GET.get('search', '').strip()[:100],
    }
    if f['category']:
        products = products.filter(catagory__name__iexact=f['category'])
    if f['min_price'] is not None:
        products = products.filter(selling_price__gte=f['min_price'])
    if f['max_price'] is not None:
        products = products.filter(selling_price__lte=f['max_price'])
    if f['vendor']:
        products = products.filter(vendor=f['vendor'])
    if f['trending']:
        products = products.filter(Trending=True)
    if f['in_stock']:
        products = products.filter(quantity__gt=0)
    relevance = None
    f['corrections'] = {}
    if f['search']:
        result = catalog_search.search(f['search'], products)
        f['corrections'] = result.parsed.corrections
        relevance = result.ids
        products = products.filter(pk__in=relevance)
    products = services.with_ratings(products).annotate(discount=services.DISCOUNT)
    order = SORTS[f['sort'] or 'popular']
    if relevance and not f['sort']:
        # Best matches first (e.g. "latop" -> both laptops before anything else)
        products = products.order_by(Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(relevance)]))
    elif f['sort'] == 'rating':
        products = products.order_by(F('avg_rating').desc(nulls_last=True), '-rating_count', 'pk')
    else:
        products = products.order_by(*order, 'pk')
    return products, f


def _paginate(request, queryset):
    page = Paginator(queryset, PRODUCTS_PER_PAGE).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    return page, query.urlencode()


# Catalog -------------------------------------------------------------------

def _listing_context(request, products, filters, **extra):
    page, querystring = _paginate(request, products)
    query = request.GET.copy()
    query.pop('page', None)
    query.pop('sort', None)
    context = {
        'page_obj': page,
        'products': page.object_list,
        'querystring': querystring,
        'sort_querystring': query.urlencode(),
        'filters': filters,
        'sort_labels': SORT_LABELS,
        'price_buckets': PRICE_BUCKETS,
        'active_filter_count': sum(1 for k, v in filters.items() if v and k not in ('sort', 'search', 'corrections')),
    }
    context.update(extra)
    return context


def home(request):
    base = services.public_products()
    products, filters = _filter_products(request, base)
    if not any(filters.values()) and not request.GET.get('page'):
        return render(request, 'shop/index.html', {
            'rows': services.landing_rows(),
            'categories': services.visible_categories(),
        })
    return render(request, 'shop/products/listing.html', _listing_context(
        request, products, filters,
        vendors=services.visible_vendors(),
        categories=services.visible_categories(),
        heading=f'Results for "{filters["search"]}"' if filters['search'] else 'All products',
    ))


def collection(request):
    categories = Catagory.objects.visible().annotate(
        product_count=Count('products', filter=Q(products__status=False))
    )
    return render(request, 'shop/collection.html', {'category': categories})


def collectionview(request, name):
    category = Catagory.objects.visible().filter(name=name).first()
    if category is None:
        messages.error(request, 'No such category found.')
        return redirect('collection')

    base = services.public_products().filter(catagory=category)
    vendors = base.values_list('vendor', flat=True).distinct().order_by('vendor')
    products, filters = _filter_products(request, base)
    return render(request, 'shop/products/listing.html', _listing_context(
        request, products, filters,
        category=category,
        category_name=category.name,
        vendors=vendors,
        heading=category.name,
    ))


def product_details(request, cname, pname):
    product = (
        Product.objects.visible()
        .select_related('catagory')
        .filter(catagory__name=cname, catagory__status=False, name=pname)
        .first()
    )
    if product is None:
        messages.error(request, 'That product is not available.')
        return redirect('collection')

    related = (
        Product.objects.visible().filter(catagory=product.catagory, quantity__gt=0)
        .exclude(pk=product.pk).select_related('catagory').order_by('-Trending', '?')[:4]
    )
    in_cart = request.user.is_authenticated and cart.objects.filter(user=request.user, product=product).exists()
    reviews = ProductReview.objects.filter(product=product, is_published=True).select_related('user')
    my_review = reviews.filter(user=request.user).first() if request.user.is_authenticated else None
    can_review = my_review is None and services.has_purchased(request.user, product)
    return render(request, 'shop/products/productview.html', {
        'product': product,
        'related_products': services.with_ratings(related),
        'in_cart': in_cart,
        'delivery': services.delivery_window(),
        'free_shipping_threshold': settings.FREE_SHIPPING_THRESHOLD,
        'shipping_fee': settings.SHIPPING_FEE,
        'reviews': reviews[:10],
        'review_stats': services.review_stats(product),
        'my_review': my_review,
        'review_form': ReviewForm() if can_review else None,
    })


@require_POST
@login_required
def submit_review(request, product_id):
    product = get_object_or_404(services.public_products(), pk=product_id)
    if not services.has_purchased(request.user, product):
        messages.error(request, 'Only customers who bought this product can review it.')
        return redirect(product.get_absolute_url())
    if ProductReview.objects.filter(product=product, user=request.user).exists():
        messages.info(request, 'You have already reviewed this product.')
        return redirect(product.get_absolute_url())
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.product, review.user = product, request.user
        review.save()
        messages.success(request, 'Thanks! Your review is live.')
    else:
        messages.error(request, 'Please add a rating, a headline and a few words about the product.')
    return redirect(product.get_absolute_url() + '#reviews')


@require_GET
def search_suggest(request):
    term = request.GET.get('q', '').strip()[:60]
    if len(term) < 2:
        return JsonResponse({'results': []})
    products = catalog_search.search(term, services.public_products(), limit=6).products
    return JsonResponse({'results': [
        {
            'name': p.name,
            'category': p.catagory.name,
            'price': p.selling_price,
            'image': p.product_image.build_url(width=96, height=96, crop='fill', fetch_format='auto', quality='auto', secure=True),
            'url': p.get_absolute_url(),
        }
        for p in products
    ]})


# Auth ----------------------------------------------------------------------

def _safe_next(request, fallback='home'):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return target
    return reverse(fallback)


def login_page(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        if not hit('login', client_key(request), limit=10, window=300):
            messages.error(request, 'Too many login attempts. Please wait a few minutes.')
            return redirect('login')
        name = request.POST.get('username', '').strip()
        pwd = request.POST.get('password', '')
        user = authenticate(request, username=name, password=pwd)
        if user is None and '@' in name:
            match = User.objects.filter(email__iexact=name).first()
            if match:
                user = authenticate(request, username=match.username, password=pwd)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect(_safe_next(request))
        messages.error(request, 'Invalid username or password.')
        return render(request, 'shop/login.html', {'username': name, 'next': request.POST.get('next', '')}, status=400)
    return render(request, 'shop/login.html', {'next': request.GET.get('next', '')})


@require_POST
def logout_page(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, 'You have been logged out.')
    return redirect('home')


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = CustomUserForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, 'Your account is ready. Happy shopping!')
        return redirect(_safe_next(request))
    return render(request, 'shop/register.html', {'form': form, 'next': request.GET.get('next', '')})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated.')
        return redirect('profile')
    recent_orders = Order.objects.filter(user=request.user).prefetch_related('items')[:3]
    return render(request, 'shop/profile.html', {
        'form': form,
        'profile_url': get_ava_url(request.user.email, size=200),
        'recent_orders': recent_orders,
        'order_count': Order.objects.filter(user=request.user).count(),
    })


# Cart ----------------------------------------------------------------------

def _cart_payload(user, message, status=200, **extra):
    summary = services.cart_summary(services.cart_items(user))
    payload = {
        'status': message,
        'cart_count': len(summary['items']),
        'subtotal': summary['subtotal'],
        'shipping': summary['shipping'],
        'total': summary['total'],
        'savings': summary['savings'],
        'free_shipping_gap': summary['free_shipping_gap'],
    }
    payload.update(extra)
    return JsonResponse(payload, status=status)


@require_POST
@_ajax_login_required
def add_to_cart(request):
    data = _json_body(request)
    product = services.public_products().filter(pk=_int(data.get('pid'))).first()
    try:
        services.add_to_cart(request.user, product, _int(data.get('product_qty'), 1))
    except services.CartError as exc:
        return JsonResponse({'status': str(exc)}, status=exc.code)
    return _cart_payload(request.user, 'Added to cart')


@require_POST
@_ajax_login_required
def update_cart(request):
    data = _json_body(request)
    item = cart.objects.select_related('product').filter(user=request.user, pk=_int(data.get('cid'))).first()
    qty = _int(data.get('product_qty'))
    if item is None:
        return JsonResponse({'status': 'Item not found'}, status=404)
    if qty is None or qty < 1:
        return JsonResponse({'status': 'Quantity must be at least 1'}, status=400)
    if qty > item.product.max_orderable:
        return JsonResponse({'status': f'Only {item.product.max_orderable} available',
                             'product_qty': item.product_qty}, status=409)
    item.product_qty = qty
    item.save(update_fields=['product_qty'])
    return _cart_payload(request.user, 'Cart updated', line_total=item.total_cost, product_qty=qty)


@require_POST
@_ajax_login_required
def save_for_later(request, cid):
    """Move a cart line to the wishlist."""
    item = cart.objects.filter(user=request.user, pk=_int(cid)).select_related('product').first()
    if item is None:
        return JsonResponse({'status': 'Item not found'}, status=404)
    fav.objects.get_or_create(user=request.user, product=item.product)
    item.delete()
    return _cart_payload(request.user, 'Moved to your wishlist',
                         wishlist_count=fav.objects.filter(user=request.user).count())


def help_page(request):
    return render(request, 'shop/help.html', {
        'free_shipping_threshold': settings.FREE_SHIPPING_THRESHOLD,
        'shipping_fee': settings.SHIPPING_FEE,
        'delivery_min': settings.DELIVERY_MIN_DAYS,
        'delivery_max': settings.DELIVERY_MAX_DAYS,
        'max_qty': settings.MAX_QTY_PER_ITEM,
    })


@login_required
def cart_view(request):
    summary = services.cart_summary(services.cart_items(request.user))
    return render(request, 'shop/cart.html', {'summary': summary, 'ucart': summary['items']})


@require_POST
@login_required
def remove_cart(request, cid):
    deleted, _ = cart.objects.filter(user=request.user, pk=_int(cid)).delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return _cart_payload(request.user, 'Removed from cart' if deleted else 'Item not found')
    if deleted:
        messages.success(request, 'Item removed from your cart.')
    return redirect('cart')


# Wishlist ------------------------------------------------------------------

@require_POST
@_ajax_login_required
def faviteam(request):
    """Toggle a product in the wishlist."""
    data = _json_body(request)
    product = Product.objects.visible().filter(pk=_int(data.get('pid'))).first()
    if product is None:
        return JsonResponse({'status': 'No such product'}, status=404)
    deleted, _ = fav.objects.filter(user=request.user, product=product).delete()
    if deleted:
        in_wishlist = False
    else:
        fav.objects.get_or_create(user=request.user, product=product)
        in_wishlist = True
    return JsonResponse({
        'status': 'Saved to wishlist' if in_wishlist else 'Removed from wishlist',
        'in_wishlist': in_wishlist,
        'wishlist_count': fav.objects.filter(user=request.user).count(),
    })


@require_POST
@login_required
def remove_fav(request, fid):
    if fav.objects.filter(user=request.user, pk=_int(fid)).delete()[0]:
        messages.success(request, 'Removed from your wishlist.')
    return redirect('fav_page')


@login_required
def favpage(request):
    favitm = fav.objects.filter(user=request.user).select_related('product', 'product__catagory')
    return render(request, 'shop/fav.html', {'favitm': favitm})


# Checkout & orders ---------------------------------------------------------

def _payment_payload(request, order):
    """Data the browser needs to continue to payment (or to show the demo pause)."""
    if not payments.is_live_payment_enabled():
        if order.payment_status != Order.PaymentStatus.PAUSED:
            order.payment_status = Order.PaymentStatus.PAUSED
            order.save(update_fields=['payment_status', 'updated_at'])
        return {
            'mode': 'demo',
            'order_number': order.order_number,
            'amount': order.total,
            'order_url': order.get_absolute_url(),
        }

    if not order.razorpay_order_id:
        order.razorpay_order_id = payments.create_razorpay_order(order)
        order.save(update_fields=['razorpay_order_id', 'updated_at'])
    return {
        'mode': 'razorpay',
        'key': settings.RAZORPAY_KEY_ID,
        'amount': order.amount_paise,
        'currency': 'INR',
        'name': settings.SITE_NAME,
        'description': f'Order {order.order_number}',
        'razorpay_order_id': order.razorpay_order_id,
        'order_number': order.order_number,
        'prefill': {'name': order.full_name, 'email': order.email, 'contact': order.phone},
        'verify_url': reverse('payment_verify'),
        'failed_url': reverse('payment_failed'),
        'order_url': order.get_absolute_url(),
    }


@login_required
def checkout(request):
    summary = services.cart_summary(services.cart_items(request.user))
    if not summary['items']:
        messages.info(request, 'Your cart is empty.')
        return redirect('cart')

    last_order = Order.objects.filter(user=request.user).first()
    initial = {'full_name': request.user.get_full_name(), 'email': request.user.email}
    if last_order:
        initial.update({f: getattr(last_order, f) for f in CheckoutForm.Meta.fields})
    form = CheckoutForm(request.POST or None, initial=initial)

    if request.method == 'POST':
        if not form.is_valid():
            return JsonResponse({'status': 'Please fix the highlighted fields.', 'errors': form.errors}, status=400)
        try:
            order = services.create_order_from_cart(request.user, form.cleaned_data)
            payload = _payment_payload(request, order)
        except services.CheckoutError as exc:
            return JsonResponse({'status': str(exc)}, status=409)
        except payments.PaymentError as exc:
            return JsonResponse({'status': str(exc)}, status=502)
        return JsonResponse({'status': 'Order created', 'payment': payload})

    return render(request, 'shop/checkout.html', {
        'form': form,
        'summary': summary,
        'payment_live': payments.is_live_payment_enabled(),
    })


@require_POST
@login_required
def order_pay(request, order_number):
    order = get_object_or_404(Order, user=request.user, order_number=order_number)
    if not order.is_payable:
        return JsonResponse({'status': 'This order does not need payment.'}, status=409)
    try:
        return JsonResponse({'status': 'ok', 'payment': _payment_payload(request, order)})
    except payments.PaymentError as exc:
        return JsonResponse({'status': str(exc)}, status=502)


@require_POST
@login_required
def payment_verify(request):
    data = _json_body(request)
    order = Order.objects.filter(
        user=request.user, razorpay_order_id=data.get('razorpay_order_id', '')
    ).first()
    if order is None:
        return JsonResponse({'status': 'Order not found'}, status=404)
    if not payments.verify_payment_signature(
        data.get('razorpay_order_id'), data.get('razorpay_payment_id'), data.get('razorpay_signature')
    ):
        logger.warning('Invalid Razorpay signature for order %s', order.order_number)
        services.mark_payment_failed(order, 'invalid signature')
        return JsonResponse({'status': 'Payment verification failed'}, status=400)
    order = services.mark_order_paid(order.pk, data.get('razorpay_payment_id'), data.get('razorpay_signature'))
    messages.success(request, f'Payment received. Order {order.order_number} is confirmed!')
    return JsonResponse({'status': 'Payment successful', 'redirect': order.get_absolute_url()})


@require_POST
@login_required
def payment_failed(request):
    data = _json_body(request)
    order = Order.objects.filter(user=request.user, order_number=data.get('order_number', '')).first()
    if order:
        services.mark_payment_failed(order, str(data.get('reason', ''))[:200])
    return JsonResponse({'status': 'recorded'})


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """Server-to-server confirmation; covers users who close the tab before verify runs."""
    if not payments.verify_webhook_signature(request.body, request.headers.get('X-Razorpay-Signature', '')):
        return HttpResponse(status=400)
    event = _json_body(request)
    entity = (event.get('payload', {}).get('payment', {}) or {}).get('entity', {})
    rp_order_id = entity.get('order_id')
    order = Order.objects.filter(razorpay_order_id=rp_order_id).first() if rp_order_id else None
    if order is None:
        return HttpResponse(status=200)
    if event.get('event') in ('payment.captured', 'order.paid'):
        services.mark_order_paid(order.pk, entity.get('id', ''))
    elif event.get('event') == 'payment.failed':
        services.mark_payment_failed(order, entity.get('error_description', ''))
    return HttpResponse(status=200)


@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items')
    page = Paginator(orders, 10).get_page(request.GET.get('page'))
    return render(request, 'shop/orders.html', {'page_obj': page, 'orders': page.object_list})


@login_required
def order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product__catagory', 'events'),
        user=request.user, order_number=order_number,
    )
    return render(request, 'shop/order_detail.html', {
        'order': order,
        'timeline': order.tracking_timeline(),
        'payment_live': payments.is_live_payment_enabled(),
    })


@require_POST
@login_required
def order_cancel(request, order_number):
    order = get_object_or_404(Order, user=request.user, order_number=order_number)
    if order.is_cancellable:
        services.update_order_status(order, Order.Status.CANCELLED, 'Cancelled by customer')
        messages.success(request, f'Order {order.order_number} has been cancelled.')
    else:
        messages.error(request, 'This order can no longer be cancelled. Please contact support.')
    return redirect(order.get_absolute_url())


# Shop bot ------------------------------------------------------------------

def chat_page(request):
    return render(request, 'shop/chat.html')


@require_POST
@rate_limit('chat', 'CHAT_RATE_LIMIT_PER_MINUTE')
def ai_chat_api(request):
    data = _json_body(request)
    message = str(data.get('message', '')).strip()[:500]
    if not message:
        return JsonResponse({'reply': 'Please type a question.'}, status=400)
    if data.get('reset'):
        request.session.pop('chat_history', None)
        request.session.pop('chat_products', None)

    run = partial(chat_with_ai, message, history=request.session.get('chat_history', []), user=request.user,
                  audience='shop', known_products=request.session.get('chat_products', {}))

    if 'application/x-ndjson' in request.headers.get('Accept', ''):
        return _stream_agent(request, run)

    result = run()
    request.session['chat_history'] = result.history
    request.session['chat_products'] = result.known_products
    return JsonResponse({'reply': result.reply, 'actions': result.actions})


def _stream_agent(request, run):
    """Stream the agent's progress steps, then the reply, as newline-delimited JSON.

    The agent runs in a worker thread and pushes events into a queue; this response
    yields them as they arrive. SessionMiddleware has already finished by the time the
    body streams, so the conversation is saved to the session explicitly at the end.
    """
    if not request.session.session_key:
        request.session.save()
    events = queue.Queue()
    user = request.user
    _ = user.is_authenticated  # resolve the lazy user here, not on the worker thread

    def work():
        try:
            events.put({'type': 'result', 'result': run(on_event=events.put)})
        except Exception:
            logger.exception('EpicBot stream failed')
            events.put({'type': 'error'})
        finally:
            close_old_connections()
            connection.close()

    def body():
        worker = threading.Thread(target=work, name='epicbot-turn', daemon=True)
        worker.start()
        while True:
            try:
                event = events.get(timeout=90)
            except queue.Empty:
                event = {'type': 'error'}
            if event['type'] == 'result':
                result = event['result']
                request.session['chat_history'] = result.history
                request.session['chat_products'] = result.known_products
                request.session.save()
                yield json.dumps({'type': 'reply', 'reply': result.reply, 'actions': result.actions}) + '\n'
                return
            if event['type'] == 'error':
                yield json.dumps({'type': 'reply', 'error': True,
                                  'reply': 'Sorry, something went wrong. Please try again.'}) + '\n'
                return
            yield json.dumps(event, default=str) + '\n'

    response = StreamingHttpResponse(body(), content_type='application/x-ndjson')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # tell proxies (nginx/Render) not to buffer the stream
    return response


@staff_member_required
@require_POST
@rate_limit('staff_chat', 'CHAT_RATE_LIMIT_PER_MINUTE')
def staff_assistant_api(request):
    """Admin-only assistant. The only place the staff tools (e.g. sales summary) are offered."""
    data = _json_body(request)
    message = str(data.get('message', '')).strip()[:500]
    if data.get('reset'):
        request.session.pop('staff_chat_history', None)
        if not message:
            return JsonResponse({'status': 'ok'})
    if not message:
        return JsonResponse({'reply': 'Please type a question.'}, status=400)
    result = chat_with_ai(message, history=request.session.get('staff_chat_history', []),
                          user=request.user, audience='staff')
    request.session['staff_chat_history'] = result.history
    return JsonResponse({'reply': result.reply})


@require_POST
def chat_reset(request):
    request.session.pop('chat_history', None)
    request.session.pop('chat_products', None)
    return JsonResponse({'status': 'ok'})


# Admin dashboard -----------------------------------------------------------

@staff_member_required
def admin_dashboard(request):
    paid_states = [Order.Status.PAID, Order.Status.PROCESSING, Order.Status.SHIPPED,
                   Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED]
    paid = Order.objects.filter(payment_status=Order.PaymentStatus.PAID)
    since = timezone.now() - timezone.timedelta(days=13)
    daily = {
        row['day']: row for row in
        paid.filter(paid_at__gte=since).annotate(day=TruncDate('paid_at'))
        .values('day').annotate(revenue=Sum('total'), orders=Count('id'))
    }
    today = timezone.localdate()
    chart = []
    for offset in range(13, -1, -1):
        day = today - timezone.timedelta(days=offset)
        chart.append({'day': day.strftime('%d %b'), 'revenue': (daily.get(day) or {}).get('revenue') or 0})

    top_products = (
        Product.objects.filter(order_items__order__payment_status=Order.PaymentStatus.PAID)
        .annotate(sold=Sum('order_items__quantity'), revenue=Sum(F('order_items__quantity') * F('order_items__unit_price')))
        .order_by('-sold')[:5]
    )
    context = {
        'title': 'Sales dashboard',
        'stats': {
            'revenue': paid.aggregate(v=Sum('total'))['v'] or 0,
            'paid_orders': paid.count(),
            'to_fulfil': Order.objects.filter(status__in=[Order.Status.PAID, Order.Status.PROCESSING]).count(),
            'awaiting_payment': Order.objects.filter(status=Order.Status.PENDING_PAYMENT).count(),
            'on_hold': Order.objects.filter(status=Order.Status.ON_HOLD).count(),
            'customers': Order.objects.values('user').distinct().count(),
            'products': Product.objects.count(),
            'out_of_stock': Product.objects.filter(quantity__lte=0).count(),
        },
        'chart': chart,
        'chart_max': max([c['revenue'] for c in chart] + [1]),
        'recent_orders': Order.objects.select_related('user')[:8],
        'low_stock': Product.objects.filter(quantity__lte=Product.LOW_STOCK).select_related('catagory').order_by('quantity')[:8],
        'top_products': top_products,
        'status_breakdown': Order.objects.values('status').annotate(n=Count('id')).order_by('-n'),
        'paid_states': paid_states,
    }
    return render(request, 'admin/dashboard.html', context)


# SEO --------------------------------------------------------------

@cache_page(60 * 60)
def robots_txt(request):
    lines = [
        'User-agent: *',
        'Disallow: /admin/',
        'Disallow: /cart',
        'Disallow: /checkout',
        'Disallow: /orders/',
        'Disallow: /ai-chat/',
        f'Sitemap: {request.build_absolute_uri(reverse("sitemap"))}',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')

