"""Typo-tolerant, ranked product search shared by the storefront, live suggestions and EpicBot.

Pipeline for a query such as "show me latops under 50k":
  1. tokenize; join split words that exist joined in the catalog ("lap top" -> "laptop", "t shirt" -> "tshirt")
  2. drop filler words ("show", "me", ...)
  3. map each word to something the catalog knows:
       synonym ("refrigerator" -> "fridge")  |  department word ("phones" -> Mobile category filter)
       exact catalog word  |  singular form ("laptops" -> "laptop")  |  closest catalog word for typos ("latop" -> "laptop")
  4. fetch candidates from the database, then rank them in Python: products matching more of the
     query words win, name matches beat brand/category matches, which beat description matches.

The vocabulary is built from live product names, brands and category names, so typo correction
only ever suggests words that really exist in the store.
"""
import difflib
import re
from dataclasses import dataclass, field

from django.core.cache import cache
from django.db.models import Q

VOCAB_CACHE_KEY = 'shop:search-vocab'

STOPWORDS = {
    "show", "me", "some", "come", "products", "product", "items", "item", "please", "for", "under",
    "less", "than", "below", "within", "upto", "up", "to", "cheapest", "lowest", "expensive", "costly",
    "highest", "most", "price", "priced", "cost", "range", "the", "a", "an", "and", "or", "of", "in",
    "is", "are", "any", "do", "you", "have", "i", "want", "need", "looking", "find", "get", "buy",
    "best", "good", "cheap", "with", "what", "which", "can", "rs", "rupees", "my", "on", "deals",
    "cheaper", "pricier", "ones", "one", "more", "other", "others", "similar", "like", "them", "those",
    "these", "this", "that", "it", "else", "also", "too", "instead", "options", "alternatives",
    "there", "available", "stock", "sell", "selling", "shop", "store", "epicoutlet", "new", "latest",
    "top", "rated", "budget", "affordable", "premium", "quality", "online", "order", "purchase",
    "recommend", "suggest", "few", "all", "list", "see", "check", "tell", "about", "how", "much",
    "over", "above", "between", "from", "only", "just",
}

# Words that mean a department, not a product. They filter by category instead of matching text.
CATEGORY_WORDS = {
    "mobile": "Mobile", "mobiles": "Mobile", "phone": "Mobile", "phones": "Mobile",
    "smartphone": "Mobile", "smartphones": "Mobile", "cellphone": "Mobile", "handset": "Mobile",
    "fashion": "Fashion", "clothes": "Fashion", "clothing": "Fashion", "apparel": "Fashion",
    "wear": "Fashion", "outfit": "Fashion", "garments": "Fashion",
    "home": "Home", "furniture": "Home", "decor": "Home",
    "electronic": "Electronic", "electronics": "Electronic", "gadget": "Electronic",
    "gadgets": "Electronic", "appliance": "Electronic", "appliances": "Electronic",
    "grocery": "Grocery", "groceries": "Grocery", "food": "Grocery", "foods": "Grocery",
    "provisions": "Grocery", "essentials": "Grocery",
}

# Everyday words for things the catalog names differently.
SYNONYMS = {
    "refrigerator": ["fridge"], "refrigerators": ["fridge"], "freezer": ["fridge"],
    "television": ["tv"], "televisions": ["tv"], "tvs": ["tv"],
    "notebook": ["laptop"], "notebooks": ["laptop"], "macbook": ["laptop"],
    "headphone": ["headphones"], "headset": ["headphones"], "headsets": ["headphones"],
    "earphone": ["headphones"], "earphones": ["headphones"], "earbuds": ["headphones"],
    "ac": ["air", "conditioner"], "aircon": ["air", "conditioner"], "airconditioner": ["air", "conditioner"],
    "ps5": ["playstation"], "ps4": ["playstation"],
    "tee": ["tshirt"], "tees": ["tshirt"], "tshirts": ["tshirt"],
    "pants": ["jeans"], "denim": ["jeans"], "trousers": ["jeans"],
    "couch": ["sofa"], "couches": ["sofa"],
    "cupboard": ["wardrobe"], "almirah": ["wardrobe"], "closet": ["wardrobe"],
    "desk": ["table"], "cot": ["bed"],
    "atta": ["flour"], "wheat": ["flour"], "yogurt": ["curd"], "dahi": ["curd"],
}

# Weights for where a query word is found.
NAME_WORD, NAME_PART, BRAND, CATEGORY, DESCRIPTION = 6, 4, 3, 3, 1


def tokenize(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _words_with_joins(text):
    """Tokens of a catalog string plus adjacent pairs joined ("T-Shirt" -> t, shirt, tshirt)."""
    tokens = tokenize(text)
    return set(tokens) | {a + b for a, b in zip(tokens, tokens[1:])}


def vocabulary():
    """Catalog words (names, brands, categories) used for typo correction. Cached; cleared on catalog change."""
    vocab = cache.get(VOCAB_CACHE_KEY)
    if vocab is None:
        from .services import public_products  # avoid an import cycle
        words = set()
        for name, vendor, category in public_products().values_list('name', 'vendor', 'catagory__name'):
            words |= _words_with_joins(name) | _words_with_joins(vendor) | _words_with_joins(category)
        words = {w for w in words if len(w) > 1 and not w.isdigit()} | {
            w for w in words if w.isdigit()
        }
        vocab = sorted(words)
        cache.set(VOCAB_CACHE_KEY, vocab, 300)
    return vocab


def _singular(word):
    if word.endswith('ies') and len(word) > 4:
        return word[:-3] + 'y'
    if word.endswith('es') and len(word) > 4:
        return word[:-2]
    if word.endswith('s') and len(word) > 3:
        return word[:-1]
    return word


@dataclass
class ParsedQuery:
    terms: list = field(default_factory=list)          # words to match in the catalog
    category: str = None                                # department filter, if any
    corrections: dict = field(default_factory=dict)    # {"latop": "laptop"}

    @property
    def interpreted(self):
        return ' '.join(self.terms + ([self.category.lower()] if self.category else []))


def parse_query(text):
    vocab = vocabulary()
    vocab_set = set(vocab)
    tokens = [t for t in tokenize(text) if t]

    # 1. join split words that exist joined in the catalog ("lap top", "t shirt")
    joined, i = [], 0
    while i < len(tokens):
        pair = tokens[i] + tokens[i + 1] if i + 1 < len(tokens) else ''
        if pair and (pair in vocab_set or _singular(pair) in vocab_set):
            joined.append(pair if pair in vocab_set else _singular(pair))
            i += 2
        else:
            joined.append(tokens[i])
            i += 1

    parsed = ParsedQuery()
    fuzzy_pool = vocab + list(SYNONYMS) + list(CATEGORY_WORDS)
    for word in joined:
        if word in STOPWORDS or (len(word) < 2 and not word.isdigit()):
            continue
        if re.fullmatch(r"\d+k?", word) and word not in vocab_set:
            continue  # prices and quantities ("20000", "50k"), not model numbers
        resolved = _resolve(word, vocab_set, fuzzy_pool)
        if resolved is None:
            parsed.terms.append(word)  # unknown word: still try it literally
            continue
        kind, value, corrected_from = resolved
        if corrected_from:
            parsed.corrections[corrected_from] = ' '.join(value) if kind != 'category' else value.lower()
        if kind == 'category':
            parsed.category = parsed.category or value
        else:
            for term in value:
                if term not in parsed.terms:
                    parsed.terms.append(term)
    return parsed


def _resolve(word, vocab_set, fuzzy_pool):
    """('terms', [..], corrected_from) | ('category', name, corrected_from) | None."""
    def classify(candidate, corrected_from=None):
        if candidate in SYNONYMS:
            return 'terms', SYNONYMS[candidate], corrected_from
        if candidate in CATEGORY_WORDS:
            return 'category', CATEGORY_WORDS[candidate], corrected_from
        if candidate in vocab_set:
            return 'terms', [candidate], corrected_from
        return None

    found = classify(word)
    if found:
        return found
    singular = _singular(word)
    if singular != word:
        found = classify(singular)
        if found:
            return found
    if len(word) >= 3 and not word.isdigit():
        cutoff = 0.75 if len(word) >= 5 else 0.8
        match = difflib.get_close_matches(word, fuzzy_pool, n=1, cutoff=cutoff)
        if match:
            result = classify(match[0], corrected_from=word)
            if result and result[0] == 'terms':
                # report the correction in catalog words ("latop" -> "laptop")
                return 'terms', result[1], word if match[0] != word else None
            return result
    return None


def _score(product, terms):
    name_words = _words_with_joins(product.name)
    name = product.name.lower().replace('-', '').replace(' ', '')
    brand_words = _words_with_joins(product.vendor)
    category_words = _words_with_joins(product.catagory.name)
    description_words = set(tokenize(product.description))
    matched, score = 0, 0
    for term in terms:
        if term in name_words:
            points = NAME_WORD
        elif len(term) >= 3 and term in name:
            points = NAME_PART
        elif term in brand_words:
            points = BRAND
        elif term in category_words or _singular(term) in category_words:
            points = CATEGORY
        elif term in description_words:
            points = DESCRIPTION
        else:
            continue
        matched += 1
        score += points
    return matched, score


@dataclass
class SearchResult:
    products: list
    parsed: ParsedQuery

    @property
    def ids(self):
        return [p.pk for p in self.products]


MAX_CANDIDATES = 500


def _rank(queryset, terms):
    """Products in `queryset` matching the terms, best first; keeps only those matching the most terms."""
    text_filter = Q()
    for term in terms:
        text_filter |= (Q(name__icontains=term) | Q(vendor__icontains=term)
                        | Q(catagory__name__icontains=term) | Q(description__icontains=term))
    # Joined catalog words ("tshirt" for "T-Shirt") are invisible to SQL, so score a wider set then.
    candidates = list(queryset.filter(text_filter)[:MAX_CANDIDATES]) or list(queryset[:MAX_CANDIDATES])
    ranked = []
    for product in candidates:
        matched, score = _score(product, terms)
        if matched:
            ranked.append((matched, score, product.Trending, -product.pk, product))
    if not ranked:
        return []
    best = max(r[0] for r in ranked)
    ranked = [r for r in ranked if r[0] == best]  # prefer products matching every query word
    ranked.sort(key=lambda r: r[:4], reverse=True)
    return [r[4] for r in ranked]


def search(text, base_queryset, limit=None):
    """Ranked products for free text within `base_queryset` (already filtered by price, stock, etc.)."""
    parsed = parse_query(text)
    queryset = base_queryset.select_related('catagory')
    in_category = queryset.filter(catagory__name__iexact=parsed.category) if parsed.category else queryset

    if not parsed.terms:
        products = list(in_category.order_by('-Trending', '-Created_at', 'pk')) if parsed.category else []
    else:
        products = _rank(in_category, parsed.terms)
        if not products and parsed.category:
            # "samsung laptop phone": nothing matches inside the department, so search everywhere
            products = _rank(queryset, parsed.terms)
    return SearchResult(products[:limit] if limit else products, parsed)
