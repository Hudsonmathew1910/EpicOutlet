from django.urls import path, include
from . import views
from api.models import v1_api

urlpatterns = [
    path('', views.home, name="home"),
    path('register', views.register, name="register"),
    path('login', views.login_page, name="login"),
    path('logout', views.logout_page, name="logout"),
    path('collection', views.collection, name="collection"),
    path('collection/<str:name>', views.collectionview, name="collection_view"),
    # path('collection/<str:cname>/<str:pname>', views.productview, name="product_view"),
    path('collection/<str:cname>/<str:pname>/', views.product_details, name='product_view'),
    path('add-to-cart', views.add_to_cart, name="addtocart"),
    path('cart', views.cart_view, name='cart'),
    path('remove_cart/<str:cid>', views.remove_cart, name='remove_cart'),
    path('profile', views.profile, name='profile'),
    path('fav', views.faviteam, name='fav'),
    path('fav_page', views.favpage, name='fav_page'),
    path('remove_fav/<str:fid>', views.remove_fav, name='remove_fav'),
    path('one-click-import/', views.one_click_import, name='one_click_import'),
    path('api/', include(v1_api.urls)),
]

