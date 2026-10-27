from django import template

register = template.Library()


@register.filter
def cdn(image, size=600):
    """Resized, auto-format Cloudinary URL for an image field. Usage: {{ product.product_image|cdn:400 }}"""
    if not image:
        return ''
    try:
        size = int(size)
        return image.build_url(width=size, height=size, crop='fill', gravity='auto',
                               fetch_format='auto', quality='auto', secure=True)
    except Exception:
        return getattr(image, 'url', '')


@register.filter
def cdn_fit(image, size=900):
    """Like cdn, but keeps the whole image (no crop) — for product detail pages."""
    if not image:
        return ''
    try:
        return image.build_url(width=int(size), crop='limit', fetch_format='auto', quality='auto', secure=True)
    except Exception:
        return getattr(image, 'url', '')


@register.filter
def inr(value):
    """Indian digit grouping: 1234567 -> 12,34,567."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return value
    sign = '-' if value < 0 else ''
    digits = str(abs(value))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return sign + ','.join(groups) + ',' + tail


@register.filter
def percent_of(value, total):
    try:
        return min(100, round(int(value) * 100 / int(total)))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.simple_tag(takes_context=True)
def query_with(context, *pairs, **kwargs):
    """Current query string with some parameters replaced; pass None/'' to remove one. Always resets paging.

    Usage: {% query_with sort="low_high" %}  or  {% query_with "min_price" 0 "max_price" 999 %}
    """
    query = context['request'].GET.copy()
    query.pop('page', None)
    updates = dict(zip(pairs[::2], pairs[1::2]))
    updates.update(kwargs)
    for key, value in updates.items():
        if value in (None, ''):
            query.pop(key, None)
        else:
            query[key] = value
    encoded = query.urlencode()
    return '?' + encoded if encoded else '?'


@register.filter
def minus(value, other):
    try:
        return int(value) - int(other)
    except (TypeError, ValueError):
        return value
