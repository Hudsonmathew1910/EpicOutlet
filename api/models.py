from tastypie.authorization import ReadOnlyAuthorization
from tastypie.constants import ALL, ALL_WITH_RELATIONS
from tastypie.resources import ModelResource
from tastypie import fields
from tastypie.api import Api
from shop.models import Catagory, Product

# Public, read-only catalog API. Carts, wishlists and orders are only reachable
# through the authenticated storefront views.


class CatagoryResource(ModelResource):
    class Meta:
        queryset = Catagory.objects.visible()
        resource_name = 'category'
        allowed_methods = ['get']
        authorization = ReadOnlyAuthorization()
        fields = ['id', 'name', 'description', 'order']
        filtering = {'name': ALL}

    def dehydrate(self, bundle):
        bundle.data['image'] = bundle.obj.image.build_url(secure=True) if bundle.obj.image else None
        return bundle


class ProductResource(ModelResource):
    category = fields.ForeignKey(CatagoryResource, 'catagory')

    class Meta:
        queryset = Product.objects.visible().select_related('catagory')
        resource_name = 'product'
        allowed_methods = ['get']
        authorization = ReadOnlyAuthorization()
        fields = ['id', 'name', 'vendor', 'description', 'orginal_price', 'selling_price', 'Trending']
        filtering = {
            'name': ALL, 'vendor': ALL, 'selling_price': ALL, 'Trending': ALL,
            'category': ALL_WITH_RELATIONS,
        }
        ordering = ['selling_price', 'name']
        max_limit = 100

    def dehydrate(self, bundle):
        product = bundle.obj
        bundle.data['in_stock'] = product.in_stock
        bundle.data['image'] = product.product_image.build_url(secure=True) if product.product_image else None
        bundle.data['url'] = product.get_absolute_url()
        return bundle


v1_api = Api(api_name='v1')
v1_api.register(CatagoryResource())
v1_api.register(ProductResource())
