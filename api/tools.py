from shop.models import Product
from django.db.models import Q
from django.urls import reverse
import re


def search_products(
    query: str = "",
    category: str = None,
    min_price: int = None,
    max_price: int = None,
    vendor: str = None,
    trending: bool = None,
    limit: int = 5,
    sort: str = None,
    **kwargs
):
    """
    Search products safely from database.
    Returns structured data for AI usage.
    """

    products = Product.objects.filter(status=False)

    query_text = (query or "").strip()
    query_words = re.findall(r"[a-z0-9]+", query_text.lower())
    query_text_lower = query_text.lower()
    inferred_category = False
    sort_value = (sort or "").strip().lower()

    # Category filter
    if category:
        products = products.filter(catagory__name__iexact=category) # field(cat_name) = value(user val)
    elif query_text:
        CATEGORY_KEYWORDS = {
                                "mobile": [
                                        "mobile", "mobiles", "phone", "phones",
                                        "smartphone", "smartphones", "cellphone",
                                        "android phone", "iphone"
                                    ],

                                    "fashion": [
                                        "fashion", "dress", "dresses",
                                        "clothes", "clothing", "clothings",
                                        "apparel", "wear", "outfit", "garment"
                                    ],

                                    "home": [
                                        "home", "house", "furniture",
                                        "sofa", "sofas", "bed",
                                        "table", "chair", "home decor"
                                    ],

                                    "electronic": [
                                        "electronic", "electronics",
                                        "gadget", "gadgets",
                                        "device", "devices",
                                        "laptop", "tv", "computer"
                                    ],

                                    "grocery": [
                                        "grocery", "groceries",
                                        "food", "foods",
                                        "snacks", "provisions",
                                        "daily essentials", "supermarket"
                                    ]
        }
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in query_words for kw in keywords):
                category = cat
                inferred_category = True
                products = products.filter(catagory__name__iexact=category)
                break

    # Price filters
    if min_price is not None:
        products = products.filter(selling_price__gte=min_price)

    if max_price is not None:
        products = products.filter(selling_price__lte=max_price)

    # Vendor filter
    if vendor:
        products = products.filter(vendor__iexact=vendor)

    # Trending filter
    if trending:
        products = products.filter(Trending=True)

    # Text search
    if query_text:
        search_terms = query_words[:]
        if inferred_category:
            category_terms = set()
            for keywords in CATEGORY_KEYWORDS.values():
                category_terms.update(keywords)

            stopwords = {
                "show", "me", "some", "come", "products", "product",
                "items", "item", "please", "for", "under", "less", "than",
                "cheapest", "lowest", "expensive", "costly", "highest", "most",
                "price", "priced", "cost", "range"
            }
            search_terms = [
                word for word in query_words
                if word not in category_terms and word not in stopwords
            ]

        if search_terms:
            text_query = Q()
            for term in search_terms:
                text_query |= (
                    Q(name__icontains=term) |
                    Q(description__icontains=term) |
                    Q(catagory__name__icontains=term) |
                    Q(vendor__icontains=term)
                )
            products = products.filter(text_query).distinct()

    # Price sorting
    sort_asc_aliases = {"price_asc", "asc", "low_to_high", "lowest", "cheapest", "min_price"}
    sort_desc_aliases = {"price_desc", "desc", "high_to_low", "highest", "expensive", "costly", "max_price"}

    if not sort_value:
        if any(term in query_text_lower for term in ["cheapest", "lowest", "low to high", "minimum price"]):
            sort_value = "price_asc"
        elif any(term in query_text_lower for term in ["most expensive", "highest", "high to low", "maximum price"]):
            sort_value = "price_desc"

    if sort_value in sort_asc_aliases:
        products = products.order_by("selling_price")
    elif sort_value in sort_desc_aliases:
        products = products.order_by("-selling_price")

    products = products[:limit]

    results = []

    for product in products:
        results.append({
            "name": product.name,
            "category": product.catagory.name,
            "vendor": product.vendor,
            "price": product.selling_price,
            "description": product.description,
            "url": reverse("product_view", args=[product.catagory.name, product.name]),
        })

    return results
