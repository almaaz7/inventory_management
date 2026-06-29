import hashlib

from django.core.cache import cache

CACHE_VERSION_KEY = "products:cache_version"


def product_list_cache_key(request):
    """Unique key per URL query string + current cache generation."""
    version = cache.get(CACHE_VERSION_KEY, 0)
    query_string = request.META.get("QUERY_STRING", "")
    query_hash = hashlib.md5(query_string.encode()).hexdigest()
    return f"products:list:v{version}:{query_hash}"


def invalidate_product_list_cache():
    """
    Bump the cache generation so all product-list keys become stale.
    Old entries expire naturally via TTL.
    """
    try:
        cache.incr(CACHE_VERSION_KEY)
    except ValueError:
        cache.set(CACHE_VERSION_KEY, 1, timeout=None)
