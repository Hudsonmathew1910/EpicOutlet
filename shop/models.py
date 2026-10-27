from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.urls import reverse
from django.utils import timezone
import datetime
import os
import secrets
from django.contrib.auth.models import User
import hashlib
from cloudinary.models import CloudinaryField

def  getFileName(request, filename):
    now_time = datetime.datetime.now().strftime("%Y%m%d%H:%M:%S")
    new_filename = "%s_%s"%(now_time, filename)  # noqa: F509
    return os.path.join('uploads/', new_filename)

def get_ava_url(email, size=100):
    emai= (email or '').strip().lower().encode('utf-8')
    hash = hashlib.md5(emai).hexdigest()
    return f"https://www.gravatar.com/avatar/{hash}?s={size}&d=identicon"


class VisibleQuerySet(models.QuerySet):
    """`status=False` means visible in this project (0-show, 1-hidden)."""

    def visible(self):
        return self.filter(status=False)


class Catagory(models.Model):
    name = models.CharField(max_length=150, null=False, blank=False, unique=True)
    image = CloudinaryField('image', folder='Epicoutlte/catagory/')
    description = models.TextField(max_length=500, null=False, blank=False)
    status = models.BooleanField(default=False, help_text="0-show, 1-Hidden")
    Created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)

    objects = VisibleQuerySet.as_manager()

    class Meta:
        ordering = ['order']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('collection_view', args=[self.name])


class Product(models.Model):
    catagory=models.ForeignKey(Catagory, on_delete=models.CASCADE, related_name='products', verbose_name='category')
    name = models.CharField(max_length=150, null=False, blank=False)
    vendor = models.CharField(max_length=150, null=False, blank=False, db_index=True)
    product_image = CloudinaryField('image', folder='Epicoutlte/products/')
    quantity = models.IntegerField(null=False, blank=False, validators=[MinValueValidator(0)], help_text="Units in stock")
    orginal_price = models.IntegerField(null=False, blank=False, validators=[MinValueValidator(1)], verbose_name='original price')
    selling_price = models.IntegerField(null=False, blank=False, validators=[MinValueValidator(1)])
    description = models.TextField(max_length=500, null=False, blank=False)
    status = models.BooleanField(default=False, help_text="0-show, 1-Hidden")
    Trending = models.BooleanField(default=False, help_text="0-default, 1-Trending")
    Created_at = models.DateTimeField(auto_now_add=True)

    objects = VisibleQuerySet.as_manager()

    LOW_STOCK = 5

    class Meta:
        ordering = ['-Created_at']
        indexes = [
            models.Index(fields=['status', 'catagory'], name='product_visible_cat_idx'),
            models.Index(fields=['status', 'selling_price'], name='product_visible_price_idx'),
            models.Index(fields=['status', 'Trending'], name='product_visible_trend_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['catagory', 'name'], name='unique_product_name_per_category'),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('product_view', args=[self.catagory.name, self.name])

    @property
    def discount_percent(self):
        if self.orginal_price and self.orginal_price > self.selling_price:
            return round((self.orginal_price - self.selling_price) * 100 / self.orginal_price)
        return 0

    @property
    def in_stock(self):
        return self.quantity > 0

    @property
    def is_low_stock(self):
        return 0 < self.quantity <= self.LOW_STOCK

    @property
    def max_orderable(self):
        return max(0, min(self.quantity, settings.MAX_QTY_PER_ITEM))


class cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_qty=models.IntegerField(null=False, blank=False, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Cart item'
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='unique_cart_item'),
        ]

    @property
    def total_cost(self):
        return self.product_qty * self.product.selling_price


class fav(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Wishlist item'
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='unique_fav_item'),
        ]


def generate_order_number():
    return 'EO' + timezone.now().strftime('%y%m%d') + secrets.token_hex(3).upper()


phone_validator = RegexValidator(r'^[6-9]\d{9}$', 'Enter a valid 10-digit Indian mobile number.')
pincode_validator = RegexValidator(r'^[1-9]\d{5}$', 'Enter a valid 6-digit PIN code.')


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = 'pending_payment', 'Awaiting payment'
        PAID = 'paid', 'Payment received'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for delivery'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'
        ON_HOLD = 'on_hold', 'On hold'

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAUSED = 'paused', 'Paused (demo)'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    # The customer-facing tracking steps, in order.
    TRACKING_STEPS = [
        Status.PAID, Status.PROCESSING, Status.SHIPPED, Status.OUT_FOR_DELIVERY, Status.DELIVERED,
    ]

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True, default=generate_order_number, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT, db_index=True)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)

    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=10, validators=[phone_validator])
    address_line1 = models.CharField('address line 1', max_length=255)
    address_line2 = models.CharField('address line 2', max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField('PIN code', max_length=6, validators=[pincode_validator])

    subtotal = models.PositiveIntegerField(default=0)
    shipping_fee = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)

    razorpay_order_id = models.CharField(max_length=64, blank=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=64, blank=True)
    razorpay_signature = models.CharField(max_length=128, blank=True)
    tracking_number = models.CharField(max_length=64, blank=True)
    courier = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number

    def get_absolute_url(self):
        return reverse('order_detail', args=[self.order_number])

    @property
    def amount_paise(self):
        return self.total * 100

    @property
    def is_payable(self):
        return self.status == self.Status.PENDING_PAYMENT

    @property
    def is_cancellable(self):
        return self.status == self.Status.PENDING_PAYMENT

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    def tracking_timeline(self):
        """Steps for the tracking UI: each with label, done flag and timestamp."""
        events = {e.status: e.created_at for e in self.events.all()}
        if self.status in self.TRACKING_STEPS:
            reached = self.TRACKING_STEPS.index(self.status)
        else:
            reached = -1
        return [
            {
                'label': self.Status(step).label,
                'done': index <= reached,
                'current': index == reached,
                'at': events.get(step),
            }
            for index, step in enumerate(self.TRACKING_STEPS)
        ]

    def add_event(self, status, note=''):
        return OrderEvent.objects.create(order=self, status=status, note=note)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name='order_items')
    product_name = models.CharField(max_length=150)
    vendor = models.CharField(max_length=150, blank=True)
    unit_price = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    def __str__(self):
        return f'{self.product_name} x {self.quantity}'

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class ProductReview(models.Model):
    """A rating from a customer who has a paid order containing the product."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=120)
    body = models.TextField(max_length=1000)
    is_published = models.BooleanField(default=True, help_text='Untick to hide this review from the store and EpicBot')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['product', 'user'], name='one_review_per_customer'),
        ]

    def __str__(self):
        return f'{self.product} – {self.rating}★ by {self.user}'


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.order} -> {self.get_status_display()}'
