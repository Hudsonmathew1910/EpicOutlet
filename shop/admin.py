from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Catagory, Order, OrderEvent, OrderItem, Product, ProductReview, cart, fav
from . import services


def thumbnail(image, size=56):
    if not image:
        return '-'
    url = image.build_url(width=size * 2, height=size * 2, crop='fill', fetch_format='auto', quality='auto', secure=True)
    return format_html('<img src="{}" width="{}" height="{}" style="object-fit:cover;border-radius:8px" alt="">', url, size, size)


@admin.register(Catagory)
class catagoryadmin(admin.ModelAdmin):
    list_display = ('preview', 'name', 'product_total', 'order', 'status')
    list_display_links = ('preview', 'name')
    list_editable = ('order', 'status')
    search_fields = ('name',)

    @admin.display(description='Image')
    def preview(self, obj):
        return thumbnail(obj.image, 44)

    @admin.display(description='Products')
    def product_total(self, obj):
        return obj.products.count()


class StockFilter(admin.SimpleListFilter):
    title = 'stock'
    parameter_name = 'stock'

    def lookups(self, request, model_admin):
        return [('out', 'Out of stock'), ('low', f'Low (≤ {Product.LOW_STOCK})'), ('ok', 'In stock')]

    def queryset(self, request, queryset):
        if self.value() == 'out':
            return queryset.filter(quantity__lte=0)
        if self.value() == 'low':
            return queryset.filter(quantity__gt=0, quantity__lte=Product.LOW_STOCK)
        if self.value() == 'ok':
            return queryset.filter(quantity__gt=Product.LOW_STOCK)
        return queryset


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('preview', 'name', 'vendor', 'catagory', 'quantity', 'selling_price', 'discount', 'status', 'Trending')
    list_display_links = ('preview', 'name')
    list_editable = ('quantity', 'selling_price', 'status', 'Trending')
    list_filter = ('catagory', StockFilter, 'Trending', 'status', 'vendor')
    search_fields = ('name', 'vendor', 'description')
    list_select_related = ('catagory',)
    list_per_page = 25
    actions = ['mark_trending', 'unmark_trending', 'hide_products', 'show_products']
    fieldsets = (
        ('Product', {'fields': ('catagory', 'name', 'vendor', 'description', 'product_image')}),
        ('Pricing & stock', {'fields': ('orginal_price', 'selling_price', 'quantity')}),
        ('Visibility', {'fields': ('status', 'Trending')}),
    )

    @admin.display(description='Image')
    def preview(self, obj):
        return thumbnail(obj.product_image, 44)

    @admin.display(description='Off')
    def discount(self, obj):
        return f'{obj.discount_percent}%' if obj.discount_percent else '-'

    @admin.action(description='Mark as trending')
    def mark_trending(self, request, queryset):
        queryset.update(Trending=True)
        services.clear_catalog_cache()

    @admin.action(description='Remove trending')
    def unmark_trending(self, request, queryset):
        queryset.update(Trending=False)
        services.clear_catalog_cache()

    @admin.action(description='Hide from store')
    def hide_products(self, request, queryset):
        queryset.update(status=True)
        services.clear_catalog_cache()

    @admin.action(description='Show in store')
    def show_products(self, request, queryset):
        queryset.update(status=False)
        services.clear_catalog_cache()


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ('product', 'product_name', 'vendor', 'unit_price', 'quantity', 'line_total')

    def has_add_permission(self, request, obj=None):
        return False


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    can_delete = False
    readonly_fields = ('status', 'note', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


def _status_action(status, label):
    def action(modeladmin, request, queryset):
        changed = 0
        for order in queryset.exclude(status=status).exclude(status=Order.Status.CANCELLED):
            services.update_order_status(order, status, f'Updated by {request.user.username}')
            changed += 1
        modeladmin.message_user(request, f'{changed} order(s) marked as {label}.', messages.SUCCESS)
    action.__name__ = f'mark_{status}'
    action.short_description = f'Mark as {label}'
    return action


STATUS_COLOURS = {
    'pending_payment': 'secondary', 'paid': 'info', 'processing': 'primary', 'shipped': 'primary',
    'out_for_delivery': 'warning', 'delivered': 'success', 'cancelled': 'dark', 'on_hold': 'danger',
}


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'total_display', 'status_badge', 'payment_status', 'city', 'created_at')
    list_filter = ('status', 'payment_status', 'created_at', 'state')
    search_fields = ('order_number', 'user__username', 'email', 'phone', 'full_name', 'razorpay_payment_id')
    date_hierarchy = 'created_at'
    list_select_related = ('user',)
    inlines = [OrderItemInline, OrderEventInline]
    readonly_fields = ('order_number', 'user', 'subtotal', 'shipping_fee', 'total', 'payment_status',
                       'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'paid_at',
                       'created_at', 'updated_at')
    fieldsets = (
        ('Order', {'fields': ('order_number', 'user', 'status', 'created_at', 'updated_at')}),
        ('Shipping address', {'fields': ('full_name', 'email', 'phone', 'address_line1', 'address_line2', 'city', 'state', 'pincode')}),
        ('Fulfilment', {'fields': ('courier', 'tracking_number')}),
        ('Payment', {'fields': ('subtotal', 'shipping_fee', 'total', 'payment_status', 'paid_at',
                                'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature')}),
    )
    actions = [
        _status_action(Order.Status.PROCESSING, 'processing'),
        _status_action(Order.Status.SHIPPED, 'shipped'),
        _status_action(Order.Status.OUT_FOR_DELIVERY, 'out for delivery'),
        _status_action(Order.Status.DELIVERED, 'delivered'),
        _status_action(Order.Status.CANCELLED, 'cancelled'),
    ]

    @admin.display(description='Customer', ordering='user__username')
    def customer(self, obj):
        return obj.full_name or obj.user.username

    @admin.display(description='Total', ordering='total')
    def total_display(self, obj):
        return f'₹{obj.total:,}'

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        return format_html('<span class="badge bg-{}">{}</span>', STATUS_COLOURS.get(obj.status, 'secondary'), obj.get_status_display())

    def save_model(self, request, obj, form, change):
        status_changed = change and 'status' in form.changed_data
        super().save_model(request, obj, form, change)
        if status_changed:
            obj.add_event(obj.status, f'Updated by {request.user.username}')

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(cart)
class cartadmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'product_qty', 'created_at')
    list_select_related = ('user', 'product')
    search_fields = ('user__username', 'product__name')


@admin.register(fav)
class favadmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    list_select_related = ('user', 'product')
    search_fields = ('user__username', 'product__name')


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'stars', 'title', 'is_published', 'created_at')
    list_editable = ('is_published',)
    list_filter = ('is_published', 'rating', 'created_at')
    search_fields = ('product__name', 'user__username', 'title', 'body')
    list_select_related = ('product', 'user')
    readonly_fields = ('product', 'user', 'rating', 'created_at', 'updated_at')

    @admin.display(description='Rating', ordering='rating')
    def stars(self, obj):
        return '★' * obj.rating + '☆' * (5 - obj.rating)
