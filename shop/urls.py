from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include, reverse_lazy
from . import views
from .sitemaps import sitemaps
from api.models import v1_api

AUTH_TEMPLATE = 'shop/auth/form_page.html'

urlpatterns = [
    path('', views.home, name="home"),
    path('register', views.register, name="register"),
    path('login', views.login_page, name="login"),
    path('logout', views.logout_page, name="logout"),
    path('collection', views.collection, name="collection"),
    path('collection/<str:name>', views.collectionview, name="collection_view"),
    path('collection/<str:cname>/<str:pname>/', views.product_details, name='product_view'),
    path('search/suggest', views.search_suggest, name='search_suggest'),
    path('products/<int:product_id>/review', views.submit_review, name='submit_review'),

    path('add-to-cart', views.add_to_cart, name="addtocart"),
    path('cart', views.cart_view, name='cart'),
    path('cart/update', views.update_cart, name='update_cart'),
    path('cart/save-for-later/<str:cid>', views.save_for_later, name='save_for_later'),
    path('help', views.help_page, name='help'),
    path('remove_cart/<str:cid>', views.remove_cart, name='remove_cart'),
    path('profile', views.profile, name='profile'),
    path('fav', views.faviteam, name='fav'),
    path('fav_page', views.favpage, name='fav_page'),
    path('remove_fav/<str:fid>', views.remove_fav, name='remove_fav'),

    path('checkout', views.checkout, name='checkout'),
    path('orders/', views.order_list, name='orders'),
    path('orders/<str:order_number>/', views.order_detail, name='order_detail'),
    path('orders/<str:order_number>/pay', views.order_pay, name='order_pay'),
    path('orders/<str:order_number>/cancel', views.order_cancel, name='order_cancel'),
    path('payments/razorpay/verify', views.payment_verify, name='payment_verify'),
    path('payments/razorpay/failed', views.payment_failed, name='payment_failed'),
    path('payments/razorpay/webhook', views.razorpay_webhook, name='razorpay_webhook'),

    path('account/password/change/', auth_views.PasswordChangeView.as_view(
        template_name=AUTH_TEMPLATE, success_url=reverse_lazy('password_change_done'),
        extra_context={'page_title': 'Change password', 'submit_label': 'Update password'}), name='password_change'),
    path('account/password/change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name=AUTH_TEMPLATE, extra_context={'page_title': 'Password updated',
                                                    'done_message': 'Your password has been changed.'}),
        name='password_change_done'),
    path('account/password/reset/', auth_views.PasswordResetView.as_view(
        template_name=AUTH_TEMPLATE, email_template_name='shop/email/password_reset.txt',
        subject_template_name='shop/email/password_reset_subject.txt',
        extra_context={'page_title': 'Reset password', 'submit_label': 'Send reset link',
                       'intro': "Enter your account email and we'll send you a reset link."}),
        name='password_reset'),
    path('account/password/reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name=AUTH_TEMPLATE, extra_context={'page_title': 'Check your inbox',
                                                    'done_message': 'If that email has an account, a reset link is on its way.'}),
        name='password_reset_done'),
    path('account/password/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name=AUTH_TEMPLATE, extra_context={'page_title': 'Choose a new password', 'submit_label': 'Save password'}),
        name='password_reset_confirm'),
    path('account/password/reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name=AUTH_TEMPLATE, extra_context={'page_title': 'Password reset',
                                                    'done_message': 'Your password has been set. You can log in now.'}),
        name='password_reset_complete'),

    path('api/', include(v1_api.urls)),
    path('chat/', views.chat_page, name='chat'),
    path('ai-chat/', views.ai_chat_api, name='ai_chat_api'),
    path('ai-chat/reset', views.chat_reset, name='chat_reset'),

    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', views.robots_txt, name='robots'),
]
