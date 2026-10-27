from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Catagory, Product
from .services import clear_catalog_cache


@receiver([post_save, post_delete], sender=Catagory)
@receiver([post_save, post_delete], sender=Product)
def invalidate_catalog_cache(**kwargs):
    clear_catalog_cache()
