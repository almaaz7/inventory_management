import random
import uuid
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max, Min
from django.utils import timezone
from faker import Faker

from catalog.models import Category, Product, Supplier


class Command(BaseCommand):
    help = "Bulk seed products for performance testing (uses existing categories and suppliers)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--products",
            type=int,
            default=5000,
            help="Number of products to create (default: 5000). Use 0 with --refresh-dates only.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Rows per bulk batch (default: 500).",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Optional random seed for reproducible data.",
        )
        parser.add_argument(
            "--refresh-dates",
            action="store_true",
            help="Re-randomize created_at on existing SEED-* products.",
        )

    def handle(self, *args, **options):
        count = options["products"]
        batch_size = options["batch_size"]
        seed = options["seed"]
        refresh_dates = options["refresh_dates"]

        if count < 0:
            raise CommandError("--products must be 0 or greater.")

        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1.")

        if count == 0 and not refresh_dates:
            raise CommandError("Pass --refresh-dates when --products is 0.")

        fake = self._make_faker(seed)

        if refresh_dates:
            self._refresh_seed_created_at(fake, batch_size)

        if count == 0:
            return

        categories = list(Category.objects.filter(is_active=True))
        suppliers = list(Supplier.objects.all())

        if not categories:
            raise CommandError("No active categories found. Create categories first.")
        if not suppliers:
            raise CommandError("No suppliers found. Create suppliers first.")

        self.stdout.write(
            f"Seeding {count} products "
            f"({len(categories)} categories, {len(suppliers)} suppliers)..."
        )

        through_model = Product.supplier.through
        created_total = 0

        for batch_start in range(0, count, batch_size):
            batch_count = min(batch_size, count - batch_start)
            products = []

            for _ in range(batch_count):
                products.append(
                    Product(
                        name=fake.catch_phrase(),
                        sku=f"SEED-{uuid.uuid4().hex[:12].upper()}",
                        description=fake.paragraph(nb_sentences=3),
                        price=Decimal(str(round(random.uniform(10, 9999.99), 2))),
                        category=random.choice(categories),
                        is_active=random.random() > 0.05,
                    )
                )

            Product.objects.bulk_create(products)
            self._assign_created_at(products, fake)
            Product.objects.bulk_update(products, ["created_at"])
            created_total += batch_count

            through_rows = []
            max_suppliers = min(2, len(suppliers))
            for product in products:
                chosen = random.sample(
                    suppliers,
                    k=random.randint(1, max_suppliers),
                )
                for supplier in chosen:
                    through_rows.append(
                        through_model(
                            product_id=product.id,
                            supplier_id=supplier.id,
                        )
                    )

            through_model.objects.bulk_create(through_rows, ignore_conflicts=True)

            self.stdout.write(f"  ... {created_total}/{count}", ending="\r")
            self.stdout.flush()

        total = Product.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCreated {created_total} products. Total in database: {total}."
            )
        )

    def _make_faker(self, seed):
        if seed is not None:
            random.seed(seed)
            fake = Faker()
            Faker.seed(seed)
            return fake
        return Faker()

    def _random_created_at(self, fake):
        return fake.date_time_between(
            start_date="-2y",
            end_date="now",
            tzinfo=timezone.get_current_timezone(),
        )

    def _assign_created_at(self, products, fake):
        for product in products:
            product.created_at = self._random_created_at(fake)

    def _refresh_seed_created_at(self, fake, batch_size):
        queryset = Product.objects.filter(sku__startswith="SEED-").order_by("id")
        total = queryset.count()

        if total == 0:
            self.stdout.write("No SEED-* products to refresh.")
            return

        self.stdout.write(f"Refreshing created_at on {total} SEED-* products...")

        updated = 0
        batch = []
        for product in queryset.iterator(chunk_size=batch_size):
            batch.append(product)
            if len(batch) >= batch_size:
                self._assign_created_at(batch, fake)
                Product.objects.bulk_update(batch, ["created_at"])
                updated += len(batch)
                self.stdout.write(f"  ... {updated}/{total}", ending="\r")
                self.stdout.flush()
                batch = []

        if batch:
            self._assign_created_at(batch, fake)
            Product.objects.bulk_update(batch, ["created_at"])
            updated += len(batch)

        stats = queryset.aggregate(earliest=Min("created_at"), latest=Max("created_at"))
        self.stdout.write(
            self.style.SUCCESS(
                f"\nRefreshed {updated} products. "
                f"Range: {stats['earliest']} → {stats['latest']}."
            )
        )
