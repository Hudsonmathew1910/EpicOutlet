from django.db import models
from tastypie.resources import ModelResource
from shop.models import Catagory, Product, cart, fav
from tastypie.api import Api

class CatagoryResource(ModelResource):
    class Meta:
        queryset = Catagory.objects.all()
        resource_name = 'category'
        allowed_methods = ['get', 'post', 'put', 'delete']  
        
class ProductResource(ModelResource):
    class Meta:
        queryset = Product.objects.all()
        resource_name = 'product'
        allowed_methods = ['get', 'post', 'put', 'delete']

class CartResource(ModelResource):
    class Meta:
        queryset = cart.objects.all()
        resource_name = 'cart'
        allowed_methods = ['get', 'post', 'put', 'delete']

class FavResource(ModelResource):
    class Meta:
        queryset = fav.objects.all()
        resource_name = 'favorite'
        allowed_methods = ['get', 'post', 'put', 'delete']
        
v1_api = Api(api_name='v1')
v1_api.register(CatagoryResource())
v1_api.register(ProductResource())
v1_api.register(CartResource())
v1_api.register(FavResource())