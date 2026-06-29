import logging

from celery import shared_task
from django.core.cache import cache
from django.core.mail import send_mail

from .models import Product

logger = logging.getLogger(__name__)


@shared_task
def low_stock_scan(threshold=20):
    low_stock_products = Product.objects.filter(
        is_active=True,
        current_stock__lt=threshold,
    )

    if not low_stock_products.exists():
        logger.info("Low-stock scan completed: All products are well stocked.")
        return "No low stock products found."

    report_lines = [f"LOW STOCK REPORT (Threshold: {threshold})"]
    for product in low_stock_products:
        report_lines.append(
            f"- {product.name} (SKU: {product.sku}) | Current Stock: {product.current_stock}"
        )

    report = "\n".join(report_lines)
    logger.warning(report)
    return f"Report generated for {low_stock_products.count()} products."


@shared_task
def notify_supplier(product_id, stock_movement_id, threshold=20):
    lock_key = f"notified_movement:{stock_movement_id}"

    is_unique_execution = cache.add(lock_key, "sent", timeout=86400)

    if not is_unique_execution:
        return "Duplicate execution blocked."

    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        cache.delete(lock_key)
        return f"Product {product_id} not found."

    stock = product.current_stock

    if stock < threshold:
        suppliers = product.supplier.all()
        if not suppliers.exists():
            return f"Product {product.name} is low, but has no assigned suppliers."

        for supplier in suppliers:
            send_mail(
                subject=f"URGENT: Low Stock Alert - {product.name}",
                message=(
                    f"Hello {supplier.name},\n\n"
                    f"This is an automated notification that {product.name} (SKU: {product.sku}) "
                    f"has dropped below our minimum threshold.\n"
                    f"Current Stock: {stock}\n\n"
                    f"Please arrange a restock shipment as soon as possible."
                ),
                from_email='inventory@yourcompany.com',
                recipient_list=[supplier.email],
                fail_silently=False,
            )
        return f"Dispatched low stock alerts to {suppliers.count()} suppliers for {product.name}."

    cache.delete(lock_key)
    return f"{product.name} stock level ({stock}) is safe."
