"""Cart, order and catalog logic shared by views, webhooks and the shop bot."""
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q, Sum
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Catagory, Order, OrderItem, Product, ProductReview, cart, fav

logger = logging.getLogger(__name__)

CATEGORY_CACHE_KEY = 'shop:categories'
VENDOR_CACHE_KEY = 'shop:vendors'
LANDING_CACHE_KEY = 'shop:landing'


class CheckoutError(Exception):
    pass


class CartError(Exception):
    """A cart change that breaks a store rule. `code` is the HTTP status a web view should use."""

    def __init__(self, message, code=409):
        super().__init__(message)
        self.code = code


# Catalog -------------------------------------------------------------------

def public_products():
    """Products a customer may see: the product is shown AND its category is shown."""
    return Product.objects.visible().filter(catagory__status=False).select_related('catagory')


PUBLISHED_REVIEWS = Q(reviews__is_published=True)
DISCOUNT = ExpressionWrapper(
    (F('orginal_price') - F('selling_price')) * 100.0 / F('orginal_price'), output_field=FloatField()
)


def with_ratings(queryset):
    """Annotate avg_rating / rating_count (published reviews only) in the same query."""
    return queryset.annotate(
        avg_rating=Avg('reviews__rating', filter=PUBLISHED_REVIEWS),
        rating_count=Count('reviews', filter=PUBLISHED_REVIEWS),
    )


def landing_rows():
    """Home page shelves. Three queries, cached for two minutes (cleared when the catalog changes)."""
    rows = cache.get(LANDING_CACHE_KEY)
    if rows is None:
        base = with_ratings(public_products().filter(quantity__gt=0))
        deals = list(base.filter(orginal_price__gt=F('selling_price')).annotate(discount=DISCOUNT)
                     .order_by('-discount', 'pk')[:12])
        trending = list(base.filter(Trending=True).order_by('-Created_at', 'pk')[:12])
        by_category = {}
        for product in base.order_by('catagory__order', '-Trending', '-Created_at', 'pk')[:120]:
            shelf = by_category.setdefault(product.catagory_id, {'category': product.catagory, 'products': []})
            if len(shelf['products']) < 10:
                shelf['products'].append(product)
        rows = {'deals': deals, 'trending': trending, 'categories': list(by_category.values())}
        cache.set(LANDING_CACHE_KEY, rows, 120)
    return rows


def visible_categories():
    categories = cache.get(CATEGORY_CACHE_KEY)
    if categories is None:
        categories = list(Catagory.objects.visible())
        cache.set(CATEGORY_CACHE_KEY, categories, 300)
    return categories


def visible_vendors():
    vendors = cache.get(VENDOR_CACHE_KEY)
    if vendors is None:
        vendors = list(
            Product.objects.visible().values_list('vendor', flat=True).distinct().order_by('vendor')
        )
        cache.set(VENDOR_CACHE_KEY, vendors, 300)
    return vendors


def clear_catalog_cache():
    cache.delete_many([CATEGORY_CACHE_KEY, VENDOR_CACHE_KEY, LANDING_CACHE_KEY, 'shop:search-vocab'])


# Cart ----------------------------------------------------------------------

def cart_items(user):
    return (
        cart.objects.filter(user=user)
        .select_related('product', 'product__catagory')
        .order_by('-created_at')
    )


def shipping_for(subtotal):
    if subtotal == 0 or subtotal >= settings.FREE_SHIPPING_THRESHOLD:
        return 0
    return settings.SHIPPING_FEE


def cart_summary(items):
    items = list(items)
    subtotal = sum(item.total_cost for item in items)
    savings = sum(
        max(0, item.product.orginal_price - item.product.selling_price) * item.product_qty for item in items
    )
    shipping = shipping_for(subtotal)
    problems = [
        item for item in items
        if item.product.status or item.product_qty > item.product.quantity
    ]
    return {
        'items': items,
        'count': sum(item.product_qty for item in items),
        'subtotal': subtotal,
        'savings': savings,
        'shipping': shipping,
        'total': subtotal + shipping,
        'free_shipping_gap': max(0, settings.FREE_SHIPPING_THRESHOLD - subtotal) if subtotal else 0,
        'free_shipping_threshold': settings.FREE_SHIPPING_THRESHOLD,
        'problems': problems,
    }


def add_to_cart(user, product, qty):
    """Add `qty` of a product to the user's cart, enforcing stock and per-item limits."""
    if product is None or product.status or product.catagory.status:
        raise CartError('No such product', 404)
    if qty < 1:
        raise CartError('Quantity must be at least 1', 400)
    if not product.in_stock:
        raise CartError('This product is out of stock')
    item = cart.objects.filter(user=user, product=product).first()
    new_qty = (item.product_qty if item else 0) + qty
    if new_qty > product.max_orderable:
        raise CartError(f'You can add at most {product.max_orderable} of this item')
    try:
        if item:
            item.product_qty = new_qty
            item.save(update_fields=['product_qty'])
        else:
            item = cart.objects.create(user=user, product=product, product_qty=qty)
    except IntegrityError:
        raise CartError('Please try again')
    return item


def remove_from_cart(user, product_id):
    return cart.objects.filter(user=user, product_id=product_id).delete()[0] > 0


def add_to_wishlist(user, product):
    if product is None or product.status or product.catagory.status:
        raise CartError('No such product', 404)
    _, created = fav.objects.get_or_create(user=user, product=product)
    return created


# Reviews -------------------------------------------------------------------

def has_purchased(user, product):
    if not user.is_authenticated:
        return False
    return OrderItem.objects.filter(
        order__user=user, order__payment_status=Order.PaymentStatus.PAID, product=product,
    ).exists()


def review_stats(product):
    return ProductReview.objects.filter(product=product, is_published=True).aggregate(
        average=Avg('rating'), count=Count('id'),
    )


# Delivery ------------------------------------------------------------------

def _business_days_after(start, days):
    current = start
    while days > 0:
        current += timezone.timedelta(days=1)
        if current.weekday() < 6:  # couriers deliver Mon-Sat
            days -= 1
    return current


def delivery_window(start=None):
    """Earliest/latest delivery dates for an order paid today (used on product pages)."""
    start = start or timezone.localdate()
    return {
        'earliest': _business_days_after(start, settings.DELIVERY_MIN_DAYS),
        'latest': _business_days_after(start, settings.DELIVERY_MAX_DAYS),
    }


def delivery_estimate(order):
    """Estimated delivery window for an order, as a dict for the order page or the shop bot."""
    status = order.status
    events = {e.status: e.created_at for e in order.events.all()}
    fmt = '%a, %d %b'
    if status == Order.Status.DELIVERED:
        at = events.get(Order.Status.DELIVERED, order.updated_at)
        return {'state': 'delivered', 'message': f'Delivered on {timezone.localtime(at).strftime(fmt)}.'}
    if status == Order.Status.CANCELLED:
        return {'state': 'cancelled', 'message': 'This order was cancelled, so it will not be delivered.'}
    if status == Order.Status.ON_HOLD:
        return {'state': 'on_hold', 'message': 'This order is on hold; our team will contact you shortly.'}
    if status == Order.Status.PENDING_PAYMENT:
        return {'state': 'awaiting_payment',
                'message': 'Not dispatched yet because payment is pending. Once paid, delivery usually takes '
                           f'{settings.DELIVERY_MIN_DAYS}-{settings.DELIVERY_MAX_DAYS} business days.'}
    if status == Order.Status.OUT_FOR_DELIVERY:
        return {'state': 'today', 'message': 'Out for delivery: it should arrive today.'}

    if status == Order.Status.SHIPPED:
        start = timezone.localtime(events.get(Order.Status.SHIPPED, order.updated_at)).date()
        low, high = 1, 3
    else:  # paid / processing
        start = timezone.localtime(order.paid_at or order.created_at).date()
        low, high = settings.DELIVERY_MIN_DAYS, settings.DELIVERY_MAX_DAYS
    earliest = max(_business_days_after(start, low), timezone.localdate())
    latest = max(_business_days_after(start, high), earliest)
    return {
        'state': 'in_transit' if status == Order.Status.SHIPPED else 'preparing',
        'earliest': earliest.isoformat(),
        'latest': latest.isoformat(),
        'message': f'Expected between {earliest.strftime(fmt)} and {latest.strftime(fmt)}.',
    }


# Reporting (staff only) ----------------------------------------------------

SALES_PERIODS = {'today': 0, '7d': 6, '30d': 29, '90d': 89}


def sales_summary(period='7d'):
    period = period if period in SALES_PERIODS else '7d'
    start_of_today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    since = start_of_today - timezone.timedelta(days=SALES_PERIODS[period])
    paid = Order.objects.filter(payment_status=Order.PaymentStatus.PAID, paid_at__gte=since)
    totals = paid.aggregate(revenue=Sum('total'), orders=Count('id'))
    top = (
        OrderItem.objects.filter(order__in=paid)
        .values('product_name').annotate(units=Sum('quantity'), revenue=Sum(F('quantity') * F('unit_price')))
        .order_by('-units')[:5]
    )
    revenue = totals['revenue'] or 0
    orders = totals['orders'] or 0
    return {
        'period': period,
        'from': since.date().isoformat(),
        'revenue': revenue,
        'paid_orders': orders,
        'average_order_value': round(revenue / orders) if orders else 0,
        'orders_awaiting_payment': Order.objects.filter(status=Order.Status.PENDING_PAYMENT, created_at__gte=since).count(),
        'to_fulfil_now': Order.objects.filter(status__in=[Order.Status.PAID, Order.Status.PROCESSING]).count(),
        'on_hold_now': Order.objects.filter(status=Order.Status.ON_HOLD).count(),
        'top_products': list(top),
        'out_of_stock_products': Product.objects.filter(quantity__lte=0).count(),
        'low_stock_products': list(
            Product.objects.filter(quantity__gt=0, quantity__lte=Product.LOW_STOCK).values('name', 'quantity')[:10]
        ),
    }


# Orders --------------------------------------------------------------------

@transaction.atomic
def create_order_from_cart(user, address):
    """Snapshot the user's cart into a new pending order. Stock is taken when payment succeeds."""
    items = list(cart_items(user).select_for_update())
    if not items:
        raise CheckoutError('Your cart is empty.')

    for item in items:
        product = item.product
        if product.status:
            raise CheckoutError(f'"{product.name}" is no longer available. Please remove it from your cart.')
        if item.product_qty > product.quantity:
            raise CheckoutError(
                f'Only {product.quantity} of "{product.name}" left in stock. Please update your cart.'
            )

    # A fresh checkout supersedes earlier unpaid attempts.
    for stale in Order.objects.filter(user=user, status=Order.Status.PENDING_PAYMENT).exclude(
        payment_status=Order.PaymentStatus.PAID
    ):
        update_order_status(stale, Order.Status.CANCELLED, 'Replaced by a newer checkout')

    summary = cart_summary(items)
    order = Order.objects.create(
        user=user,
        subtotal=summary['subtotal'],
        shipping_fee=summary['shipping'],
        total=summary['total'],
        **address,
    )
    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            product=item.product,
            product_name=item.product.name,
            vendor=item.product.vendor,
            unit_price=item.product.selling_price,
            quantity=item.product_qty,
        )
        for item in items
    ])
    order.add_event(Order.Status.PENDING_PAYMENT, 'Order placed')
    logger.info('Order %s created for user %s (total %s)', order.order_number, user.pk, order.total)
    return order


@transaction.atomic
def mark_order_paid(order_id, payment_id='', signature=''):
    """Idempotently record a successful payment, take stock and clear the purchased cart lines."""
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.payment_status == Order.PaymentStatus.PAID:
        return order

    order.payment_status = Order.PaymentStatus.PAID
    order.razorpay_payment_id = payment_id or order.razorpay_payment_id
    order.razorpay_signature = signature or order.razorpay_signature
    order.paid_at = timezone.now()

    short = []
    items = list(order.items.select_related('product'))
    product_ids = [i.product_id for i in items if i.product_id]
    stock = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=product_ids)}
    for item in items:
        product = stock.get(item.product_id)
        if product is None or product.quantity < item.quantity:
            short.append(item.product_name)
            continue
        Product.objects.filter(pk=product.pk).update(quantity=F('quantity') - item.quantity)

    if short:
        # Paid but we cannot fulfil everything: hold for a human to refund or restock.
        order.status = Order.Status.ON_HOLD
        order.save()
        order.add_event(Order.Status.ON_HOLD, 'Insufficient stock for: ' + ', '.join(short))
        logger.warning('Order %s paid but short on stock: %s', order.order_number, short)
    else:
        order.status = Order.Status.PAID
        order.save()
        order.add_event(Order.Status.PAID, 'Payment confirmed')

    cart.objects.filter(user=order.user, product_id__in=product_ids).delete()
    transaction.on_commit(lambda: send_order_confirmation(order))
    return order


def mark_payment_failed(order, reason=''):
    if order.payment_status != Order.PaymentStatus.PAID:
        order.payment_status = Order.PaymentStatus.FAILED
        order.save(update_fields=['payment_status', 'updated_at'])
        logger.info('Payment failed for order %s: %s', order.order_number, reason)


def update_order_status(order, status, note=''):
    order.status = status
    order.save(update_fields=['status', 'updated_at'])
    order.add_event(status, note)


def send_order_confirmation(order):
    try:
        body = render_to_string('shop/email/order_confirmation.txt', {'order': order})
        send_mail(f'Your EpicOutlet order {order.order_number}', body, None, [order.email], fail_silently=False)
    except Exception:
        logger.exception('Could not send confirmation email for %s', order.order_number)
