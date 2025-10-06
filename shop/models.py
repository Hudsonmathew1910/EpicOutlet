from django.db import models
import datetime
import os
from django.contrib.auth.models import User
import hashlib

def  getFileName(request, filename):
    now_time = datetime.datetime.now().strftime("%Y%m%d%H:%M:%S")
    new_filename = "%s_%s"%(now_time, filename)  # noqa: F509
    return os.path.join('uploads/', new_filename)

def get_ava_url(email, size=100):
    emai= email.strip().lower().encode('utf-8')
    hash = hashlib.md5(emai).hexdigest()
    return f"https://www.gravatar.com/avatar/{hash}?s={size}&d=identicon"

class Catagory(models.Model):
    name = models.CharField(max_length=150, null=False, blank=False)
    image = models.ImageField(upload_to=getFileName, null=False, blank=False)
    description = models.TextField(max_length=500, null=False, blank=False)
    status = models.BooleanField(default=False, help_text="0-show, 1-Hidden")
    Created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order'] 
    
    def __str__(self):
        return self.name
    
class Product(models.Model):
    catagory=models.ForeignKey(Catagory, on_delete=models.CASCADE)
    name = models.CharField(max_length=150, null=False, blank=False)
    vendor = models.CharField(max_length=150, null=False, blank=False)
    product_image = models.ImageField(upload_to=getFileName, null=False, blank=False)
    quantity = models.IntegerField(null=False, blank=False)
    orginal_price = models.IntegerField(null=False, blank=False)
    selling_price = models.IntegerField(null=False, blank=False)
    description = models.TextField(max_length=500, null=False, blank=False)
    status = models.BooleanField(default=False, help_text="0-show, 1-Hidden")
    Trending = models.BooleanField(default=False, help_text="0-default, 1-Trending")
    Created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_qty=models.IntegerField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def total_cost(self):
        return self.product_qty * self.product.selling_price
    
class fav(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)