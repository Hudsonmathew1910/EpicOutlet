import hashlib
import hmac
import json
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from . import services
from .models import Catagory, Order, Product, ProductReview, cart, fav

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
ADDRESS = {
    'full_name': 'Asha Rao', 'email': 'asha@example.com', 'phone': '9876543210',
    'address_line1': '12 MG Road', 'address_line2': '', 'city': 'Bengaluru',
    'state': 'Karnataka', 'pincode': '560001',
}


class ShopTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cat = Catagory.objects.create(name='Mobile', image='sample', description='Phones')
        cls.hidden_cat = Catagory.objects.create(name='Secret', image='sample', description='Hidden', status=True)
        cls.phone = Product.objects.create(
            catagory=cls.cat, name='Galaxy A55', vendor='Samsung', product_image='sample',
            quantity=5, orginal_price=40000, selling_price=30000, description='A great phone', Trending=True,
        )
        cls.cheap = Product.objects.create(
            catagory=cls.cat, name='Redmi 13', vendor='Xiaomi', product_image='sample',
            quantity=20, orginal_price=500, selling_price=400, description='Budget phone',
        )
        cls.hidden = Product.objects.create(
            catagory=cls.cat, name='Prototype', vendor='Samsung', product_image='sample',
            quantity=5, orginal_price=100, selling_price=100, description='Not for sale', status=True,
        )
        cls.user = User.objects.create_user('asha', 'asha@example.com', 'S3cure-pass!')
        cls.other = User.objects.create_user('ravi', 'ravi@example.com', 'S3cure-pass!')

    def post_json(self, url, data=None, **extra):
        return self.client.post(url, json.dumps(data or {}), content_type='application/json', **AJAX, **extra)


class CatalogTests(ShopTestCase):
    def test_home_lists_only_visible_products(self):
        res = self.client.get(reverse('home'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Galaxy A55')
        self.assertNotContains(res, 'Prototype')

    def test_filters_and_sort(self):
        res = self.client.get(reverse('home'), {'max_price': 1000})
        self.assertEqual([p.name for p in res.context['products']], ['Redmi 13'])
        res = self.client.get(reverse('home'), {'sort': 'high_low'})
        self.assertEqual(res.context['products'][0].name, 'Galaxy A55')
        res = self.client.get(reverse('home'), {'search': 'phones'})
        self.assertEqual(res.context['page_obj'].paginator.count, 2)

    def test_bad_filter_values_do_not_crash(self):
        res = self.client.get(reverse('home'), {'min_price': 'abc', 'sort': 'DROP TABLE', 'page': '999'})
        self.assertEqual(res.status_code, 200)

    def test_product_detail_and_seo(self):
        res = self.client.get(self.phone.get_absolute_url())
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '"@type": "Product"')
        self.assertContains(res, '25% off')

    def test_hidden_product_and_category_redirect(self):
        res = self.client.get(self.hidden.get_absolute_url())
        self.assertRedirects(res, reverse('collection'))
        res = self.client.get(reverse('collection_view', args=['Secret']))
        self.assertRedirects(res, reverse('collection'))

    def test_search_suggest(self):
        res = self.client.get(reverse('search_suggest'), {'q': 'galaxy'})
        self.assertEqual(res.json()['results'][0]['name'], 'Galaxy A55')

    def test_sitemap_and_robots(self):
        self.assertContains(self.client.get(reverse('sitemap')), 'Galaxy%20A55')
        self.assertContains(self.client.get(reverse('robots')), 'Sitemap:')

    def test_404_page(self):
        res = self.client.get('/no-such-page/')
        self.assertEqual(res.status_code, 404)


class AuthTests(ShopTestCase):
    def test_register_logs_in(self):
        res = self.client.post(reverse('register'), {
            'username': 'newbie', 'email': 'new@example.com',
            'password1': 'Very-strong-123', 'password2': 'Very-strong-123',
        })
        self.assertRedirects(res, reverse('home'))
        self.assertTrue(User.objects.filter(username='newbie').exists())

    def test_register_rejects_duplicate_email(self):
        res = self.client.post(reverse('register'), {
            'username': 'dupe', 'email': 'ASHA@example.com',
            'password1': 'Very-strong-123', 'password2': 'Very-strong-123',
        })
        self.assertContains(res, 'already exists')

    def test_login_with_email_and_safe_next(self):
        res = self.client.post(reverse('login'), {'username': 'asha@example.com', 'password': 'S3cure-pass!', 'next': '/cart'})
        self.assertRedirects(res, '/cart', fetch_redirect_response=False)
        self.client.logout()
        res = self.client.post(reverse('login'), {'username': 'asha', 'password': 'S3cure-pass!', 'next': 'https://evil.com'})
        self.assertRedirects(res, reverse('home'))

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)


class CartTests(ShopTestCase):
    def test_add_requires_login(self):
        res = self.post_json(reverse('addtocart'), {'pid': self.phone.pk, 'product_qty': 1})
        self.assertEqual(res.status_code, 401)

    def test_add_merges_and_respects_stock(self):
        self.client.force_login(self.user)
        self.assertEqual(self.post_json(reverse('addtocart'), {'pid': self.phone.pk, 'product_qty': 2}).status_code, 200)
        self.assertEqual(self.post_json(reverse('addtocart'), {'pid': self.phone.pk, 'product_qty': 2}).status_code, 200)
        self.assertEqual(cart.objects.get(user=self.user).product_qty, 4)
        res = self.post_json(reverse('addtocart'), {'pid': self.phone.pk, 'product_qty': 2})
        self.assertEqual(res.status_code, 409)

    def test_cannot_add_hidden_or_garbage(self):
        self.client.force_login(self.user)
        self.assertEqual(self.post_json(reverse('addtocart'), {'pid': self.hidden.pk}).status_code, 404)
        self.assertEqual(self.post_json(reverse('addtocart'), {'pid': 'x'}).status_code, 404)
        res = self.client.post(reverse('addtocart'), 'not json', content_type='application/json', **AJAX)
        self.assertEqual(res.status_code, 404)

    def test_update_quantity(self):
        self.client.force_login(self.user)
        item = cart.objects.create(user=self.user, product=self.cheap, product_qty=1)
        res = self.post_json(reverse('update_cart'), {'cid': item.pk, 'product_qty': 3})
        self.assertEqual(res.json()['subtotal'], 1200)
        self.assertEqual(res.json()['shipping'], 0)

    def test_cannot_touch_someone_elses_cart(self):
        item = cart.objects.create(user=self.other, product=self.cheap, product_qty=1)
        self.client.force_login(self.user)
        self.post_json(reverse('update_cart'), {'cid': item.pk, 'product_qty': 3})
        self.client.post(reverse('remove_cart', args=[item.pk]))
        item.refresh_from_db()
        self.assertEqual(item.product_qty, 1)

    def test_remove_requires_post(self):
        self.client.force_login(self.user)
        item = cart.objects.create(user=self.user, product=self.cheap, product_qty=1)
        self.assertEqual(self.client.get(reverse('remove_cart', args=[item.pk])).status_code, 405)
        self.client.post(reverse('remove_cart', args=[item.pk]))
        self.assertFalse(cart.objects.filter(pk=item.pk).exists())

    def test_shipping_fee_below_threshold(self):
        self.client.force_login(self.user)
        cart.objects.create(user=self.user, product=self.cheap, product_qty=1)
        res = self.client.get(reverse('cart'))
        self.assertEqual(res.context['summary']['shipping'], 49)
        self.assertEqual(res.context['summary']['total'], 449)


class WishlistTests(ShopTestCase):
    def test_toggle(self):
        self.client.force_login(self.user)
        res = self.post_json(reverse('fav'), {'pid': self.phone.pk})
        self.assertTrue(res.json()['in_wishlist'])
        res = self.post_json(reverse('fav'), {'pid': self.phone.pk})
        self.assertFalse(res.json()['in_wishlist'])
        self.assertFalse(fav.objects.exists())

    def test_cannot_remove_someone_elses(self):
        item = fav.objects.create(user=self.other, product=self.phone)
        self.client.force_login(self.user)
        self.client.post(reverse('remove_fav', args=[item.pk]))
        self.assertTrue(fav.objects.filter(pk=item.pk).exists())


@override_settings(PAYMENT_DEMO_MODE=True)
class DemoCheckoutTests(ShopTestCase):
    def setUp(self):
        self.client.force_login(self.user)
        cart.objects.create(user=self.user, product=self.phone, product_qty=2)

    def test_checkout_page(self):
        res = self.client.get(reverse('checkout'))
        self.assertContains(res, 'Demo store')

    def test_checkout_validates_address(self):
        res = self.client.post(reverse('checkout'), {**ADDRESS, 'phone': '123', 'pincode': '0'}, **AJAX)
        self.assertEqual(res.status_code, 400)
        self.assertIn('phone', res.json()['errors'])
        self.assertIn('pincode', res.json()['errors'])
        self.assertFalse(Order.objects.exists())

    def test_checkout_pauses_payment_in_demo_mode(self):
        res = self.client.post(reverse('checkout'), ADDRESS, **AJAX)
        self.assertEqual(res.status_code, 200)
        payment = res.json()['payment']
        self.assertEqual(payment['mode'], 'demo')

        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAUSED)
        self.assertEqual(order.total, 60000)
        self.assertEqual(order.items.get().quantity, 2)
        # Nothing charged: stock untouched and cart kept.
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.quantity, 5)
        self.assertTrue(cart.objects.filter(user=self.user).exists())

    def test_new_checkout_supersedes_unpaid_order(self):
        self.client.post(reverse('checkout'), ADDRESS, **AJAX)
        self.client.post(reverse('checkout'), ADDRESS, **AJAX)
        self.assertEqual(Order.objects.filter(status=Order.Status.PENDING_PAYMENT).count(), 1)
        self.assertEqual(Order.objects.filter(status=Order.Status.CANCELLED).count(), 1)

    def test_checkout_rejects_insufficient_stock(self):
        Product.objects.filter(pk=self.phone.pk).update(quantity=1)
        res = self.client.post(reverse('checkout'), ADDRESS, **AJAX)
        self.assertEqual(res.status_code, 409)
        self.assertFalse(Order.objects.exists())

    def test_order_pages_and_cancel(self):
        self.client.post(reverse('checkout'), ADDRESS, **AJAX)
        order = Order.objects.get()
        self.assertContains(self.client.get(reverse('orders')), order.order_number)
        self.assertContains(self.client.get(order.get_absolute_url()), 'Payment paused')
        res = self.post_json(reverse('order_pay', args=[order.order_number]))
        self.assertEqual(res.json()['payment']['mode'], 'demo')
        self.client.post(reverse('order_cancel', args=[order.order_number]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_other_users_cannot_see_order(self):
        self.client.post(reverse('checkout'), ADDRESS, **AJAX)
        order = Order.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 404)


@override_settings(PAYMENT_DEMO_MODE=False, RAZORPAY_KEY_ID='rzp_test_key', RAZORPAY_KEY_SECRET='secret',
                   RAZORPAY_WEBHOOK_SECRET='whsecret')
class RazorpayTests(ShopTestCase):
    def setUp(self):
        self.client.force_login(self.user)
        cart.objects.create(user=self.user, product=self.phone, product_qty=2)
        cart.objects.create(user=self.user, product=self.cheap, product_qty=1)

    def start_checkout(self):
        fake = mock.Mock(status_code=200)
        fake.json.return_value = {'id': 'order_RP123'}
        with mock.patch('shop.payments.requests.post', return_value=fake) as post:
            res = self.client.post(reverse('checkout'), ADDRESS, **AJAX)
        self.assertEqual(post.call_args.kwargs['json']['amount'], 60400 * 100)
        return res.json()['payment']

    def sign(self, order_id, payment_id):
        return hmac.new(b'secret', f'{order_id}|{payment_id}'.encode(), hashlib.sha256).hexdigest()

    def test_live_checkout_and_verify(self):
        payment = self.start_checkout()
        self.assertEqual(payment['mode'], 'razorpay')
        self.assertEqual(payment['razorpay_order_id'], 'order_RP123')

        with self.captureOnCommitCallbacks(execute=True):
            res = self.post_json(reverse('payment_verify'), {
                'razorpay_order_id': 'order_RP123', 'razorpay_payment_id': 'pay_1',
                'razorpay_signature': self.sign('order_RP123', 'pay_1'),
            })
        self.assertEqual(res.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.quantity, 3)
        self.assertFalse(cart.objects.filter(user=self.user).exists())
        self.assertEqual(len(mail.outbox), 1)

        # Replaying the same confirmation must not take stock twice.
        self.post_json(reverse('payment_verify'), {
            'razorpay_order_id': 'order_RP123', 'razorpay_payment_id': 'pay_1',
            'razorpay_signature': self.sign('order_RP123', 'pay_1'),
        })
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.quantity, 3)

    def test_forged_signature_is_rejected(self):
        self.start_checkout()
        res = self.post_json(reverse('payment_verify'), {
            'razorpay_order_id': 'order_RP123', 'razorpay_payment_id': 'pay_1', 'razorpay_signature': 'forged',
        })
        self.assertEqual(res.status_code, 400)
        order = Order.objects.get()
        self.assertEqual(order.payment_status, Order.PaymentStatus.FAILED)
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)

    def test_webhook_confirms_payment(self):
        self.start_checkout()
        body = json.dumps({'event': 'payment.captured', 'payload': {'payment': {'entity': {'id': 'pay_9', 'order_id': 'order_RP123'}}}}).encode()
        bad = self.client.post(reverse('razorpay_webhook'), body, content_type='application/json', HTTP_X_RAZORPAY_SIGNATURE='nope')
        self.assertEqual(bad.status_code, 400)
        sig = hmac.new(b'whsecret', body, hashlib.sha256).hexdigest()
        ok = self.client.post(reverse('razorpay_webhook'), body, content_type='application/json', HTTP_X_RAZORPAY_SIGNATURE=sig)
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(Order.objects.get().payment_status, Order.PaymentStatus.PAID)

    def test_paid_order_short_on_stock_goes_on_hold(self):
        self.start_checkout()
        Product.objects.filter(pk=self.phone.pk).update(quantity=1)
        services.mark_order_paid(Order.objects.get().pk, 'pay_2')
        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.ON_HOLD)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)

    def test_gateway_error_is_reported(self):
        fake = mock.Mock(status_code=401, text='bad key')
        with mock.patch('shop.payments.requests.post', return_value=fake):
            res = self.client.post(reverse('checkout'), ADDRESS, **AJAX)
        self.assertEqual(res.status_code, 502)


class AdminTests(ShopTestCase):
    def test_dashboard_requires_staff(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 302)

    def test_dashboard_and_order_admin_render(self):
        admin = User.objects.create_superuser('boss', 'boss@example.com', 'S3cure-pass!')
        order = Order.objects.create(user=self.user, total=100, subtotal=100, **ADDRESS)
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:shop_order_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:shop_order_change', args=[order.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:shop_product_changelist')).status_code, 200)


class ApiTests(ShopTestCase):
    def test_catalog_is_read_only_and_hides_hidden(self):
        res = self.client.get('/api/v1/product/?format=json')
        names = [p['name'] for p in res.json()['objects']]
        self.assertIn('Galaxy A55', names)
        self.assertNotIn('Prototype', names)
        res = self.client.delete(f'/api/v1/product/{self.phone.pk}/')
        self.assertEqual(res.status_code, 405)
        self.assertTrue(Product.objects.filter(pk=self.phone.pk).exists())

    def test_cart_api_removed(self):
        self.assertEqual(self.client.get('/api/v1/cart/?format=json').status_code, 404)


@override_settings(HEROS_API_KEY='', GROQ_API_KEY='')
def fake_completion(*texts):
    """A mock OpenAI client whose replies are `texts`, in order (prompted protocol)."""
    client = mock.Mock()
    client.chat.completions.create.side_effect = [
        mock.Mock(choices=[mock.Mock(message=mock.Mock(content=t, tool_calls=None))]) for t in texts
    ]
    return client


HEROS = dict(HEROS_API_KEY='k', HEROS_BASE_URL='https://heros.example/v1', HEROS_MODEL='m', GROQ_API_KEY='')


def call(tool_name, **arguments):
    return '<tool_call>' + json.dumps({'tool': tool_name, 'arguments': arguments}) + '</tool_call>'


class ChatTests(ShopTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_offline_fallback_searches_catalog(self):
        res = self.post_json(reverse('ai_chat_api'), {'message': 'phones under 1000'})
        self.assertEqual(res.status_code, 200)
        reply = res.json()['reply']
        self.assertIn('Redmi 13', reply)
        self.assertNotIn('Galaxy A55', reply)

    def test_order_question_needs_login(self):
        res = self.post_json(reverse('ai_chat_api'), {'message': 'where is my order'})
        self.assertIn('log in', res.json()['reply'])

    def test_history_kept_in_session(self):
        self.post_json(reverse('ai_chat_api'), {'message': 'samsung'})
        self.assertEqual(len(self.client.session['chat_history']), 2)

    def test_rejects_get_and_empty(self):
        self.assertEqual(self.client.get(reverse('ai_chat_api')).status_code, 405)
        self.assertEqual(self.post_json(reverse('ai_chat_api'), {'message': '  '}).status_code, 400)

    @override_settings(CHAT_RATE_LIMIT_PER_MINUTE=2)
    def test_rate_limit(self):
        codes = [self.post_json(reverse('ai_chat_api'), {'message': 'hi'}).status_code for _ in range(3)]
        self.assertEqual(codes[-1], 429)

    def test_history_keeps_last_eight_messages(self):
        from api import chat_service
        history = []
        with mock.patch.object(chat_service, '_providers', return_value=[]):
            for q in ['one', 'two', 'three', 'four', 'five']:
                history = chat_service.chat_with_ai(q, history, None).history
        self.assertEqual(len(history), 8)
        self.assertEqual([m['content'] for m in history if m['role'] == 'user'], ['two', 'three', 'four', 'five'])

    def test_follow_up_prefetch_uses_previous_question(self):
        from api.chat_service import _prefetch
        from api.tools import search_products
        self.assertEqual(search_products(query='any cheaper ones?'), [])
        history = [{'role': 'user', 'content': 'samsung phones'}, {'role': 'assistant', 'content': '...'}]
        self.assertEqual([p['name'] for p in _prefetch('any cheaper ones?', history, 'shop')['products']], ['Galaxy A55'])

    def test_unmentioned_products_are_not_appended(self):
        from api.chat_service import _normalize_links_to_paths
        products = [{'name': 'Galaxy A55', 'url': '/collection/Mobile/Galaxy%20A55/'}]
        self.assertNotIn('Product links', _normalize_links_to_paths('I only help with shopping.', products))
        self.assertIn('(/collection/Mobile/Galaxy%20A55/)', _normalize_links_to_paths('Try the Galaxy A55.', products))


@override_settings(**HEROS)
class AgentLoopTests(ShopTestCase):
    def run_agent(self, client, message, user=None, audience='shop'):
        from api import chat_service
        with mock.patch.object(chat_service, '_client', return_value=client):
            return chat_service.chat_with_ai(message, [], user, audience)

    def test_multi_step_compare_then_add_to_cart(self):
        client = fake_completion(
            call('compare_products', product_ids=[self.phone.pk, self.cheap.pk]),
            call('add_to_cart', product_id=self.cheap.pk, quantity=2),
            'Added 2 x Redmi 13 (₹400 each). It is the cheaper option.',
        )
        result = self.run_agent(client, 'compare them and add 2 of the cheaper one', self.user)
        self.assertEqual(result.provider, 'heros')
        self.assertEqual(result.tools_used, ['compare_products', 'add_to_cart'])
        self.assertEqual(cart.objects.get(user=self.user).product_qty, 2)
        self.assertEqual(result.actions['cart_count'], 1)
        self.assertIn('(/collection/Mobile/Redmi%2013/)', result.reply)  # forgotten link added from tool data
        sent = client.chat.completions.create.call_args.kwargs
        self.assertEqual(sent['extra_body'], {'type': 'text', 'search': False})
        self.assertIn('TOOL_RESULTS', sent['messages'][-1]['content'])

    def test_customer_tools_need_login(self):
        client = fake_completion(call('add_to_cart', product_id=self.phone.pk), 'Please log in first.')
        result = self.run_agent(client, 'add the galaxy to my cart')
        self.assertFalse(cart.objects.exists())
        results = client.chat.completions.create.call_args.kwargs['messages'][-1]['content']
        self.assertIn('not logged in', results)
        self.assertEqual(result.actions, {})

    def test_staff_tool_is_never_offered_to_public_bot(self):
        staff = User.objects.create_user('boss', 'boss@example.com', 'S3cure-pass!', is_staff=True)
        client = fake_completion(call('get_sales_summary', period='7d'), 'I cannot share that.')
        self.run_agent(client, 'show sales', staff, audience='shop')
        first_prompt = client.chat.completions.create.call_args_list[0].kwargs['messages'][0]['content']
        self.assertNotIn('get_sales_summary', first_prompt)
        results = client.chat.completions.create.call_args.kwargs['messages'][-1]['content']
        self.assertIn("is not available", results)

    def test_model_cannot_pick_another_users_data(self):
        services.add_to_cart(self.other, self.phone, 1)
        other_order = services.create_order_from_cart(self.other, ADDRESS)
        client = fake_completion(
            call('get_delivery_estimate', order_number=other_order.order_number, user_id=self.other.pk),
            'No such order.',
        )
        self.run_agent(client, f'when will {other_order.order_number} arrive', self.user)
        results = client.chat.completions.create.call_args.kwargs['messages'][-1]['content']
        self.assertIn('No order with that number on this account', results)

    def test_no_second_provider_after_a_write(self):
        from api import chat_service
        heros = fake_completion(call('add_to_cart', product_id=self.cheap.pk))
        heros.chat.completions.create.side_effect = list(heros.chat.completions.create.side_effect) + [RuntimeError('timeout')]
        groq = mock.Mock()
        providers = [('heros', 'u', 'k', 'm', 'prompted'), ('groq', 'u', 'k', 'm', 'native')]
        with mock.patch.object(chat_service, '_providers', return_value=providers), \
                mock.patch.object(chat_service, '_client', side_effect=[heros, groq]):
            result = chat_service.chat_with_ai('add a redmi', [], self.user)
        groq.chat.completions.create.assert_not_called()
        self.assertEqual(cart.objects.get(user=self.user).product_qty, 1)
        self.assertIn('Added **Redmi 13**', result.reply)

    def test_falls_back_to_groq_native_tools(self):
        from api import chat_service
        heros = mock.Mock()
        heros.chat.completions.create.side_effect = RuntimeError('down')
        tool_call = mock.Mock(id='c1')
        tool_call.function.name = 'get_active_offers'
        tool_call.function.arguments = '{}'
        groq = mock.Mock()
        groq.chat.completions.create.side_effect = [
            mock.Mock(choices=[mock.Mock(message=mock.Mock(content='', tool_calls=[tool_call]))]),
            mock.Mock(choices=[mock.Mock(message=mock.Mock(content='Galaxy A55 is 25% off', tool_calls=None))]),
        ]
        providers = [('heros', 'u', 'k', 'm', 'prompted'), ('groq', 'u', 'k', 'm', 'native')]
        with mock.patch.object(chat_service, '_providers', return_value=providers), \
                mock.patch.object(chat_service, '_client', side_effect=[heros, groq]):
            result = chat_service.chat_with_ai('any deals?', [], None)
        self.assertEqual(result.provider, 'groq')
        self.assertEqual(result.tools_used, ['get_active_offers'])
        self.assertIn('/collection/Mobile/Galaxy%20A55/', result.reply)

    def test_chat_endpoint_returns_actions(self):
        from api import chat_service
        self.client.force_login(self.user)
        client = fake_completion(call('add_to_wishlist', product_id=self.phone.pk), 'Saved!')
        with mock.patch.object(chat_service, '_client', return_value=client):
            res = self.post_json(reverse('ai_chat_api'), {'message': 'save the galaxy'})
        self.assertEqual(res.json()['actions'], {'wishlist_count': 1})


class AgentToolTests(ShopTestCase):
    def ctx(self, user=None):
        from api.tools import ToolContext
        return ToolContext(user=user)

    def tool(self, name, args, user=None, audience='shop'):
        from api.tools import run_tool, tools_for
        return run_tool(name, args, self.ctx(user), tools_for(audience, user))

    def test_product_details_hides_products_in_hidden_categories(self):
        Product.objects.create(
            catagory=self.hidden_cat, name='Secret Phone', vendor='Samsung', product_image='sample',
            quantity=5, orginal_price=100, selling_price=90, description='x',
        )
        self.assertIn('error', self.tool('get_product_details', {'name': 'Secret Phone'}))
        self.assertIn('error', self.tool('get_product_details', {'name': 'Prototype'}))
        self.assertEqual(self.tool('get_product_details', {'name': 'galaxy'})['name'], 'Galaxy A55')

    def test_arguments_are_validated(self):
        self.assertIn('whole number', self.tool('add_to_cart', {'quantity': 'lots'}, self.user)['error'])
        self.assertIn('not available', self.tool('run_sql', {'query': 'select 1'}, self.user)['error'])
        res = self.tool('search_products', {'limit': 999, 'evil': 'DROP TABLE'})
        self.assertLessEqual(len(res), 10)
        self.assertIn('must be one of', self.tool('get_sales_summary', {'period': 'forever'},
                                                  User.objects.create_user('s', is_staff=True), 'staff')['error'])

    def test_compare_and_offers(self):
        res = self.tool('compare_products', {'names': ['Galaxy A55', 'Redmi 13']})
        self.assertEqual(res['cheapest'], 'Redmi 13')
        self.assertIn('error', self.tool('compare_products', {'names': ['Galaxy A55']}))
        deals = self.tool('get_active_offers', {})['deals']
        self.assertEqual([d['name'] for d in deals], ['Galaxy A55', 'Redmi 13'])  # 25% off before 20% off

    def test_cart_tools_respect_stock_rules(self):
        self.assertIn('at most', self.tool('add_to_cart', {'name': 'Galaxy A55', 'quantity': 9}, self.user)['error'])
        self.assertEqual(self.tool('add_to_cart', {'name': 'redmi', 'quantity': 3}, self.user)['quantity_in_cart'], 3)
        self.assertEqual(self.tool('view_my_cart', {}, self.user)['subtotal'], 1200)
        self.assertTrue(self.tool('remove_from_cart', {'name': 'redmi'}, self.user)['removed'])
        self.assertFalse(cart.objects.filter(user=self.user).exists())

    def test_delivery_estimate_is_scoped_to_user(self):
        services.add_to_cart(self.user, self.phone, 1)
        order = services.create_order_from_cart(self.user, ADDRESS)
        mine = self.tool('get_delivery_estimate', {}, self.user)
        self.assertEqual(mine['order_number'], order.order_number)
        self.assertEqual(mine['state'], 'awaiting_payment')
        services.mark_order_paid(order.pk, 'pay_1')
        self.assertEqual(self.tool('get_delivery_estimate', {'order_number': order.order_number}, self.user)['state'], 'preparing')
        self.assertIn('error', self.tool('get_delivery_estimate', {'order_number': order.order_number}, self.other))

    def test_sales_summary_is_staff_only(self):
        staff = User.objects.create_user('boss', 'boss@example.com', 'x', is_staff=True)
        self.assertIn('not available', self.tool('get_sales_summary', {}, staff, 'shop')['error'])
        self.assertIn('revenue', self.tool('get_sales_summary', {'period': '30d'}, staff, 'staff'))
        from api.tools import tools_for
        self.assertEqual(tools_for('staff', self.user), {})

    def test_staff_assistant_endpoint(self):
        self.client.force_login(self.user)
        res = self.post_json(reverse('staff_assistant_api'), {'message': 'sales?'})
        self.assertEqual(res.status_code, 302)  # non-staff are sent to the admin login
        staff = User.objects.create_user('boss', 'boss@example.com', 'x', is_staff=True)
        self.client.force_login(staff)
        from api import chat_service
        with mock.patch.object(chat_service, '_providers', return_value=[]):
            res = self.post_json(reverse('staff_assistant_api'), {'message': 'sales?'})
        self.assertIn('7-day summary', res.json()['reply'])


class ReviewTests(ShopTestCase):
    def buy(self, user, product):
        services.add_to_cart(user, product, 1)
        order = services.create_order_from_cart(user, ADDRESS)
        services.mark_order_paid(order.pk, 'pay_x')

    def test_only_verified_buyers_can_review(self):
        self.client.force_login(self.user)
        url = reverse('submit_review', args=[self.phone.pk])
        data = {'rating': 5, 'title': 'Great', 'body': 'Love it'}
        self.client.post(url, data)
        self.assertFalse(ProductReview.objects.exists())
        self.buy(self.user, self.phone)
        self.client.post(url, data)
        self.client.post(url, data)  # a second review is refused
        self.assertEqual(ProductReview.objects.count(), 1)
        page = self.client.get(self.phone.get_absolute_url())
        self.assertContains(page, 'Certified buyer')

    def test_review_tool_shows_only_published(self):
        from api.tools import get_product_reviews
        ProductReview.objects.create(product=self.phone, user=self.user, rating=4, title='Good', body='Nice')
        ProductReview.objects.create(product=self.phone, user=self.other, rating=1, title='Spam', body='x', is_published=False)
        res = get_product_reviews(product_id=self.phone.pk)
        self.assertEqual(res['review_count'], 1)
        self.assertEqual(res['average_rating'], 4)
        self.assertEqual([r['title'] for r in res['reviews']], ['Good'])


class ToolArgumentAliasTests(ShopTestCase):
    def test_common_argument_aliases_are_accepted(self):
        from api.tools import ToolContext, run_tool, tools_for
        res = run_tool('add_to_cart', {'product_name': 'Redmi 13', 'qty': 2, 'user_id': self.other.pk},
                       ToolContext(user=self.user), tools_for('shop', self.user))
        self.assertEqual(res['quantity_in_cart'], 2)
        self.assertEqual(res['ignored_arguments'], ['user_id'])
        self.assertTrue(cart.objects.filter(user=self.user).exists())
        self.assertFalse(cart.objects.filter(user=self.other).exists())


class WriteGuardTests(ShopTestCase):
    def add(self, ctx, **args):
        from api.tools import run_tool, tools_for
        return run_tool('add_to_cart', args, ctx, tools_for('shop', self.user))

    def test_guessed_id_is_refused(self):
        from api.tools import ToolContext
        ctx = ToolContext(user=self.user)
        self.assertIn('has not been shown', self.add(ctx, product_id=self.cheap.pk)['error'])
        self.assertFalse(cart.objects.exists())

    def test_id_and_name_must_agree(self):
        from api.tools import ToolContext
        ctx = ToolContext(user=self.user, known_products={self.cheap.pk: 'Redmi 13'})
        res = self.add(ctx, product_id=self.cheap.pk, name='Galaxy A55')
        self.assertIn('is "Redmi 13", not "Galaxy A55"', res['error'])
        self.assertFalse(cart.objects.exists())

    def test_id_shown_by_an_earlier_tool_is_accepted(self):
        from api.tools import ToolContext, run_tool, tools_for
        ctx = ToolContext(user=self.user)
        run_tool('search_products', {'query': 'redmi'}, ctx, tools_for('shop', self.user))
        self.assertEqual(self.add(ctx, product_id=self.cheap.pk)['added'], 'Redmi 13')

    @override_settings(**HEROS)
    def test_known_products_survive_between_turns_via_session(self):
        from api import chat_service
        self.client.force_login(self.user)
        first = fake_completion(call('search_products', query='redmi'), 'Redmi 13 is ₹400.')
        second = fake_completion(call('add_to_cart', product_id=self.cheap.pk), 'Added.')
        with mock.patch.object(chat_service, '_client', side_effect=[first, second]):
            self.post_json(reverse('ai_chat_api'), {'message': 'show me redmi'})
            self.post_json(reverse('ai_chat_api'), {'message': 'add it to my cart'})
        self.assertEqual(cart.objects.get(user=self.user).product, self.cheap)


class PromptedParserTests(ShopTestCase):
    def parse(self, text):
        from api.chat_service import _parse_prompted_calls
        from api.tools import tools_for
        return _parse_prompted_calls(text, tools_for('shop', None))

    def test_accepts_the_shapes_models_send(self):
        expected = [('compare_products', {'names': ['A', 'B']})]
        self.assertEqual(self.parse('<tool_call>{"tool": "compare_products", "arguments": {"names": ["A", "B"]}}</tool_call>'), expected)
        self.assertEqual(self.parse('<tool_call>{"tool": "compare_products", "names": ["A", "B"]}</tool_call>'), expected)
        self.assertEqual(self.parse('<tool_call>{"name": "compare_products", "args": "{\\"names\\": [\\"A\\", \\"B\\"]}"}</tool_call>'), expected)
        self.assertEqual(self.parse('```json\n{"tool": "compare_products", "parameters": {"names": ["A", "B"]}}\n```'), expected)
        self.assertEqual(self.parse('Sure! Here are some phones.'), [])

    @override_settings(**HEROS)
    def test_failed_write_is_never_reported_as_success(self):
        from api import chat_service
        client = fake_completion(call('add_to_wishlist', name='No Such Thing'), 'Saved it to your wishlist!')
        with mock.patch.object(chat_service, '_client', return_value=client):
            result = chat_service.chat_with_ai('save no such thing', [], self.user)
        self.assertFalse(fav.objects.exists())
        self.assertIn('Nothing was changed in your cart or wishlist', result.reply)


@override_settings(**HEROS)
class TurnBudgetTests(ShopTestCase):
    def test_slow_provider_falls_back_within_budget(self):
        from api import chat_service
        client = fake_completion(call('search_products', query='redmi'), 'never reached')
        with mock.patch.object(chat_service, '_client', return_value=client), \
                mock.patch.object(chat_service, 'TURN_BUDGET_SECONDS', 0):
            result = chat_service.chat_with_ai('redmi phones', [], None)
        client.chat.completions.create.assert_not_called()
        self.assertEqual(result.provider, 'offline')
        self.assertIn('Redmi 13', result.reply)


@override_settings(**HEROS)
class AgentProgressTests(ShopTestCase):
    def test_steps_describe_what_the_agent_does(self):
        from api import chat_service
        events = []
        client = fake_completion(
            call('search_products', query='redmi', max_price=1000),
            call('add_to_cart', name='Redmi 13', quantity=2),
            'Added 2 × Redmi 13.',
        )
        with mock.patch.object(chat_service, '_client', return_value=client):
            chat_service.chat_with_ai('add 2 redmi phones under 1000', [], self.user, on_event=events.append)
        finished = [e for e in events if e['state'] != 'running']
        labels = [e.get('label') for e in events if e['state'] == 'running']
        self.assertIn('Searching products for “redmi” · under ₹1,000', labels)
        self.assertIn('Adding 2 × Redmi 13 to your cart', labels)
        details = [e.get('detail') for e in finished]
        self.assertIn('Found 1 product', details)
        self.assertTrue(any(d and d.startswith('Added · cart has 1 item(s)') for d in details))
        chips = [p for e in finished for p in e.get('products', [])]
        self.assertIn({'name': 'Redmi 13', 'url': '/collection/Mobile/Redmi%2013/'}, chips)
        # every step that starts also finishes
        started = {e['id'] for e in events if e['state'] == 'running'}
        self.assertEqual(started, {e['id'] for e in finished})

    def test_failed_step_is_marked(self):
        from api import chat_service
        events = []
        client = fake_completion(call('add_to_cart', name='Nope Phone'), 'Sorry.')
        with mock.patch.object(chat_service, '_client', return_value=client):
            chat_service.chat_with_ai('add nope phone', [], self.user, on_event=events.append)
        self.assertTrue(any(e['state'] == 'failed' and 'No such product' in e.get('detail', '') for e in events))


class ChatStreamTests(ShopTestCase):
    def test_streams_steps_then_reply_and_saves_session(self):
        from api.chat_service import AgentReply

        def fake_agent(message, on_event=None, **kwargs):
            on_event({'type': 'step', 'id': 's1', 'state': 'running', 'label': 'Searching products for “redmi”'})
            on_event({'type': 'step', 'id': 's1', 'state': 'done', 'detail': 'Found 1 product'})
            history = [{'role': 'user', 'content': message}, {'role': 'assistant', 'content': 'Redmi 13!'}]
            return AgentReply('Redmi 13!', history, {'cart_count': 1}, [], 'heros', {self.cheap.pk: 'Redmi 13'})

        with mock.patch('shop.views.chat_with_ai', side_effect=fake_agent):
            res = self.post_json(reverse('ai_chat_api'), {'message': 'redmi'}, HTTP_ACCEPT='application/x-ndjson')
            self.assertEqual(res['Content-Type'], 'application/x-ndjson')
            lines = [json.loads(line) for line in b''.join(res.streaming_content).decode().splitlines()]
        self.assertEqual([e['type'] for e in lines], ['step', 'step', 'reply'])
        self.assertEqual(lines[-1], {'type': 'reply', 'reply': 'Redmi 13!', 'actions': {'cart_count': 1}})
        session = self.client.session
        self.assertEqual(session['chat_history'][-1]['content'], 'Redmi 13!')
        self.assertEqual({str(k): v for k, v in session['chat_products'].items()}, {str(self.cheap.pk): 'Redmi 13'})

    def test_json_clients_still_get_json(self):
        res = self.post_json(reverse('ai_chat_api'), {'message': 'phones under 1000'})
        self.assertEqual(res['Content-Type'], 'application/json')
        self.assertIn('Redmi 13', res.json()['reply'])


class SearchEngineTests(ShopTestCase):
    """The "latop" bug: typos, plurals, synonyms and product-type words must find the right products."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.electronic = Catagory.objects.create(name='Electronic', image='sample', description='Gadgets')
        make = lambda name, vendor, price=1000: Product.objects.create(  # noqa: E731
            catagory=cls.electronic, name=name, vendor=vendor, product_image='sample',
            quantity=5, orginal_price=price + 100, selling_price=price, description='Great value')
        cls.hp = make('HP Laptop', 'HP', 45000)
        cls.samsung_laptop = make('Samsung Laptop', 'Samsung', 55000)
        cls.fridge = make('Fridge', 'Whirlpool', 23000)
        cls.tv = make('LG Smart TV 43', 'LG', 30000)
        cls.headphones = make('Apple Headphones', 'Apple', 2700)

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # the vocabulary is cached per catalog

    def names(self, query):
        from shop.search import search
        from shop.services import public_products
        return [p.name for p in search(query, public_products()).products]

    def test_typos_find_the_product(self):
        for query in ['latop', 'labtop', 'show me latop', 'laptops', 'lap top', 'latop under 50k']:
            with self.subTest(query=query):
                self.assertCountEqual(self.names(query), ['HP Laptop', 'Samsung Laptop'])
        self.assertEqual(self.names('headfone'), ['Apple Headphones'])
        self.assertEqual(self.names('galxy'), ['Galaxy A55'])

    def test_product_words_are_not_swallowed_by_category_guessing(self):
        # Before the fix, "laptop" meant "Electronic category" and listed the fridge and TV instead.
        self.assertCountEqual(self.names('laptop'), ['HP Laptop', 'Samsung Laptop'])
        self.assertEqual(self.names('tv'), ['LG Smart TV 43'])

    def test_synonyms_and_departments(self):
        self.assertEqual(self.names('refrigerator'), ['Fridge'])
        self.assertEqual(self.names('television'), ['LG Smart TV 43'])
        self.assertEqual(self.names('samsung phone'), ['Galaxy A55'])  # not the Samsung laptop
        self.assertCountEqual(self.names('samsung'), ['Galaxy A55', 'Samsung Laptop'])

    def test_hidden_and_unknown_products_stay_hidden(self):
        self.assertEqual(self.names('prototype'), [])
        self.assertEqual(self.names('xyzzy'), [])

    def test_bot_tool_reports_the_correction(self):
        from api.tools import search_catalog
        result = search_catalog(query='latop')
        self.assertEqual(result['corrected'], {'latop': 'laptop'})
        self.assertCountEqual([p['name'] for p in result['products']], ['HP Laptop', 'Samsung Laptop'])
        cheapest = search_catalog(query='cheapest latop')['products'][0]['name']
        self.assertEqual(cheapest, 'HP Laptop')

    def test_storefront_search_and_suggestions(self):
        page = self.client.get(reverse('home'), {'search': 'latop'})
        self.assertContains(page, 'HP Laptop')
        self.assertContains(page, 'Showing results for')
        self.assertNotContains(page, 'Fridge')
        suggest = self.client.get(reverse('search_suggest'), {'q': 'latop'}).json()['results']
        self.assertCountEqual([r['name'] for r in suggest], ['HP Laptop', 'Samsung Laptop'])
