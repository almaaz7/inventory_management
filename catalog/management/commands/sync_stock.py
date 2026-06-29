from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.db.models.functions import Coalesce

from catalog.models import Product


class Command(BaseCommand):
    help = "Rebuild Product.current_stock from stock movement ledger."

    def handle(self, *args, **options):
        self.stdout.write("Starting stock synchronization...")

        products = Product.objects.annotate(
            calculated_stock=Coalesce(Sum('stock_movements__quantity'), 0)
        )

        batch_size = 1000
        batch = []

        for product in products:
            product.current_stock = max(0, product.calculated_stock)
            batch.append(product)

            if len(batch) >= batch_size:
                Product.objects.bulk_update(batch, ['current_stock'])
                self.stdout.write(f"Updated {len(batch)} products...")
                batch = []

        if batch:
            Product.objects.bulk_update(batch, ['current_stock'])
            self.stdout.write(f"Updated {len(batch)} products...")

        self.stdout.write(self.style.SUCCESS("Stock synchronization completed successfully."))