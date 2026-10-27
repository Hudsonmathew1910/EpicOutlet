"""Human-readable progress steps for EpicBot, streamed to the chat UI while the agent works.

Only labels and short summaries leave the server here: never raw tool payloads,
prompts or model output.
"""
import logging

logger = logging.getLogger(__name__)

MAX_CHIPS = 6


def _rupees(value):
    try:
        return f"₹{int(value):,}"
    except (TypeError, ValueError):
        return ''


def _product_name(args, ctx):
    name = args.get('name') or args.get('product_name')
    if not name and args.get('product_id'):
        try:
            name = ctx.known_products.get(int(args['product_id']))
        except (TypeError, ValueError):
            name = None
    return name or 'the product'


def describe_call(name, args, ctx):
    """What the agent is about to do, e.g. 'Searching products for “samsung phone” · under ₹30,000'."""
    args = args if isinstance(args, dict) else {}
    if name == 'search_products':
        label = f'Searching products for “{args["query"]}”' if args.get('query') else 'Browsing the catalogue'
        extras = [
            args.get('category'), args.get('vendor'),
            f'under {_rupees(args["max_price"])}' if args.get('max_price') else None,
            f'over {_rupees(args["min_price"])}' if args.get('min_price') else None,
            'bestsellers' if args.get('trending') else None,
            {'price_asc': 'cheapest first', 'price_desc': 'priciest first'}.get(args.get('sort')),
        ]
        extras = [str(e) for e in extras if e]
        return label + (' · ' + ' · '.join(extras) if extras else '')
    if name == 'get_product_details':
        return f'Checking price and stock of {_product_name(args, ctx)}'
    if name == 'compare_products':
        names = list(args.get('names') or [])
        for pid in args.get('product_ids') or []:
            try:
                names.append(ctx.known_products.get(int(pid), f'#{pid}'))
            except (TypeError, ValueError):
                continue
        return 'Comparing ' + ' vs '.join(dict.fromkeys(str(n) for n in names)) if names else 'Comparing products'
    if name == 'list_categories':
        return 'Looking up store categories'
    if name == 'get_active_offers':
        return f'Finding the best deals in {args["category"]}' if args.get('category') else 'Finding today\'s best deals'
    if name == 'get_product_reviews':
        return f'Reading customer reviews of {_product_name(args, ctx)}'
    if name == 'get_store_policies':
        return 'Checking delivery, returns and payment policies'
    if name == 'get_my_orders':
        return f'Looking up order {args["order_number"]}' if args.get('order_number') else 'Looking up your orders'
    if name == 'get_delivery_estimate':
        return (f'Estimating delivery for order {args["order_number"]}' if args.get('order_number')
                else 'Estimating delivery for your latest order')
    if name == 'view_my_cart':
        return 'Opening your cart'
    if name == 'add_to_cart':
        qty = args.get('quantity') or args.get('qty') or 1
        return f'Adding {qty} × {_product_name(args, ctx)} to your cart'
    if name == 'remove_from_cart':
        return f'Removing {_product_name(args, ctx)} from your cart'
    if name == 'add_to_wishlist':
        return f'Saving {_product_name(args, ctx)} to your wishlist'
    if name == 'get_sales_summary':
        return f'Crunching sales numbers ({args.get("period", "7d")})'
    return 'Looking something up'


def product_chips(result):
    """Up to MAX_CHIPS {name, url} product links found in a tool result."""
    found, seen = [], set()

    def walk(data):
        if isinstance(data, dict):
            url = data.get('url')
            if isinstance(data.get('name'), str) and isinstance(url, str) and url.startswith('/collection/'):
                if url not in seen:
                    seen.add(url)
                    found.append({'name': data['name'], 'url': url})
            for value in data.values():
                walk(value)
        elif isinstance(data, list):
            for value in data:
                walk(value)

    walk(result)
    return found[:MAX_CHIPS]


def summarize_result(name, result):
    """(state, detail) for a finished tool call. state is 'done' or 'failed'."""
    if isinstance(result, dict) and result.get('error'):
        return 'failed', str(result['error'])[:160]
    try:
        if name == 'search_products':
            products = result.get('products', []) if isinstance(result, dict) else result
            count = len(products)
            detail = f'Found {count} product{"s" if count != 1 else ""}' if count else 'No matching products'
            if isinstance(result, dict) and result.get('corrected'):
                fixes = ', '.join(f'“{typed}” → “{fixed}”' for typed, fixed in result['corrected'].items())
                detail += f' (understood {fixes})'
            return 'done', detail
        if name == 'compare_products':
            return 'done', f'Compared {len(result["products"])} products · cheapest is {result["cheapest"]}'
        if name == 'get_product_details':
            return 'done', f'{result["name"]} · {_rupees(result["price"])} · {result["stock"]}'
        if name == 'list_categories':
            return 'done', f'{len(result)} categories'
        if name == 'get_active_offers':
            count = len(result.get('deals', []))
            return 'done', f'Found {count} deal{"s" if count != 1 else ""}' if count else 'No deals right now'
        if name == 'get_product_reviews':
            if not result.get('review_count'):
                return 'done', 'No reviews yet'
            return 'done', f'{result["review_count"]} review(s) · average {result["average_rating"]}★'
        if name == 'get_store_policies':
            return 'done', 'Got the latest store policies'
        if name == 'get_my_orders':
            count = len(result) if isinstance(result, list) else 0
            return 'done', f'Found {count} order{"s" if count != 1 else ""}' if count else 'No orders on this account'
        if name == 'get_delivery_estimate':
            return 'done', str(result.get('message', ''))[:160]
        if name == 'view_my_cart':
            items = result.get('items', [])
            return 'done', (f'{len(items)} item(s) · total {_rupees(result.get("total"))}' if items else 'Your cart is empty')
        if name == 'add_to_cart':
            return 'done', f'Added · cart has {result["cart_items"]} item(s), {_rupees(result["cart_total"])}'
        if name == 'remove_from_cart':
            return 'done', 'Removed from your cart'
        if name == 'add_to_wishlist':
            return 'done', 'Already in your wishlist' if result.get('already_saved') else 'Saved to your wishlist'
        if name == 'get_sales_summary':
            return 'done', f'Revenue {_rupees(result["revenue"])} from {result["paid_orders"]} paid orders'
    except (KeyError, TypeError):
        pass
    return 'done', 'Done'


class Progress:
    """Collects steps and forwards them to an optional listener (the streaming view)."""

    def __init__(self, listener=None):
        self.listener = listener
        self.counter = 0

    def emit(self, **event):
        if self.listener is None:
            return
        try:
            self.listener(event)
        except Exception:  # a broken stream must never break the agent
            logger.exception('EpicBot progress listener failed')

    def start(self, label, kind='tool'):
        self.counter += 1
        step_id = f's{self.counter}'
        self.emit(type='step', id=step_id, kind=kind, state='running', label=label)
        return step_id

    def finish(self, step_id, state='done', label=None, detail=None, products=None):
        event = {'type': 'step', 'id': step_id, 'state': state}
        if label:
            event['label'] = label
        if detail:
            event['detail'] = detail
        if products:
            event['products'] = products
        self.emit(**event)
