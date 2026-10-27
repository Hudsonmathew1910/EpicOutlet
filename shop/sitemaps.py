from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Catagory, Product


class StaticSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return ['home', 'collection', 'chat', 'help']

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Catagory.objects.visible()


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Product.objects.visible().filter(catagory__status=False).select_related('catagory')

    def lastmod(self, obj):
        return obj.Created_at


sitemaps = {'static': StaticSitemap, 'categories': CategorySitemap, 'products': ProductSitemap}
