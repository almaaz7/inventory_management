from django.db.models import Sum

from catalog.models import Product, StockMovement


def recompute_product_stock(product_id):
    """Set Product.current_stock from the movement ledger (source of truth)."""
    total = (
        StockMovement.objects.filter(product_id=product_id)
        .aggregate(total=Sum('quantity'))['total']
    ) or 0
    Product.objects.filter(pk=product_id).update(current_stock=max(0, total))
