from django.contrib import admin
from .models import Catagory, Product, cart
# Register your models here.


class catagoryadmin(admin.ModelAdmin):
    list_display = ('name', 'image', 'description')
    
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'catagory', 'quantity', 'selling_price', 'status', 'Trending')

class cartadmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'product_qty', 'created_at')
    
admin.site.register(Catagory, catagoryadmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(cart, cartadmin)

