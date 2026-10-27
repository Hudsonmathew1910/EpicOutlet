from django.conf import settings

from .models import cart, fav
from .services import visible_categories


def store(request):
    """Values every storefront template needs: nav categories and cart/wishlist badges."""
    context = {
        'SITE_NAME': settings.SITE_NAME,
        'nav_categories': visible_categories(),
        'cart_count': 0,
        'wishlist_count': 0,
        'wishlist_ids': set(),
    }
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        context['cart_count'] = cart.objects.filter(user=user).count()
        wishlist_ids = set(fav.objects.filter(user=user).values_list('product_id', flat=True))
        context['wishlist_ids'] = wishlist_ids
        context['wishlist_count'] = len(wishlist_ids)
    return context
