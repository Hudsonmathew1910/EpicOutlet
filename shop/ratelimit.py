"""Small cache-backed fixed-window rate limiter."""
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


def client_key(request):
    if request.user.is_authenticated:
        return f'u{request.user.pk}'
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return 'ip' + (forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR', ''))


def hit(scope, key, limit, window=60):
    """Count one hit; return True while the caller is still under the limit."""
    cache_key = f'rl:{scope}:{key}'
    cache.add(cache_key, 0, window)
    try:
        count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, window)
        count = 1
    return count <= limit


def rate_limit(scope, limit, window=60):
    """`limit` is a number or the name of a setting holding one (read per request)."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            max_hits = getattr(settings, limit) if isinstance(limit, str) else limit
            if request.method == 'POST' and not hit(scope, client_key(request), max_hits, window):
                return JsonResponse({'status': 'Too many requests. Please slow down.', 'reply': 'You are sending messages too quickly. Please wait a minute and try again.'}, status=429)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
