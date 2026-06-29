import random
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max, Min, Sum
from django.utils import timezone
from faker import Faker

from catalog.models import Category, Product, StockMovement, Supplier


class Command(BaseCommand):
    help = "Bulk seed products for performance testing (uses existing categories and suppliers)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--products",
            type=int,
            default=5000,
            help="Number of products to create (default: 5000). Use 0 for maintenance flags only.",
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
        parser.add_argument(
            "--seed-stock",
            action="store_true",
            help="Create initial received stock movements for products with no inventory history.",
        )
        parser.add_argument(
            "--low-stock-pct",
            type=int,
            default=10,
            help="Percent of stocked products to keep at low levels (default: 10).",
        )
        parser.add_argument(
            "--low-stock-max",
            type=int,
            default=10,
            help="Upper bound for low-stock quantities, inclusive (default: 10).",
        )

    def handle(self, *args, **options):
        count = options["products"]
        batch_size = options["batch_size"]
        seed = options["seed"]
        refresh_dates = options["refresh_dates"]
        seed_stock = options["seed_stock"]
        low_stock_pct = options["low_stock_pct"]
        low_stock_max = options["low_stock_max"]

        if count < 0:
            raise CommandError("--products must be 0 or greater.")

        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1.")

        if low_stock_pct < 0 or low_stock_pct > 100:
            raise CommandError("--low-stock-pct must be between 0 and 100.")

        if low_stock_max < 1:
            raise CommandError("--low-stock-max must be at least 1.")

        maintenance = refresh_dates or seed_stock
        if count == 0 and not maintenance:
            raise CommandError(
                "Pass --refresh-dates and/or --seed-stock when --products is 0."
            )

        fake = self._make_faker(seed)
        self._low_stock_pct = low_stock_pct
        self._low_stock_max = low_stock_max

        if refresh_dates:
            self._refresh_seed_created_at(fake, batch_size)

        if seed_stock:
            self._seed_stock(batch_size)

        if count == 0:
            return

        categories = list(Category.objects.filter(is_active=True))
        suppliers = list(Supplier.objects.all())

        if not categories:
            raise CommandError("No active categories found. Create categories first.")
        if not suppliers:
            raise CommandError("No suppliers found. Create suppliers first.")

        seed_user = self._get_seed_user() if seed_stock else None

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

            if seed_stock:
                self._seed_stock_for_products(products, seed_user)

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

    def _get_seed_user(self):
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not user:
            raise CommandError(
                "No user found. Create a user first (StockMovement.created_by is required)."
            )
        return user

    def _random_stock_quantity(self):
        """Return a received quantity, or None to leave the product out of stock."""
        roll = random.random()
        low_cutoff = self._low_stock_pct / 100

        if roll < 0.03:
            return None

        if roll < 0.03 + low_cutoff:
            return random.randint(1, self._low_stock_max)

        if roll < 0.93:
            return random.randint(51, 500)

        return random.randint(501, 2000)

    def _seed_stock_for_products(self, products, user):
        movements = []
        for product in products:
            quantity = self._random_stock_quantity()
            if quantity is None:
                continue
            movements.append(
                StockMovement(
                    product=product,
                    quantity=quantity,
                    reason=StockMovement.REASON_RECEIVED,
                    created_by=user,
                )
            )
        if movements:
            StockMovement.objects.bulk_create(movements)

    def _seed_stock(self, batch_size):
        user = self._get_seed_user()
        queryset = (
            Product.objects.filter(stock_movements__isnull=True)
            .order_by("id")
            .distinct()
        )
        total = queryset.count()

        if total == 0:
            self.stdout.write("All products already have stock movements.")
            return

        self.stdout.write(f"Seeding stock for {total} products without inventory history...")

        seeded = 0
        batch = []
        for product in queryset.iterator(chunk_size=batch_size):
            batch.append(product)
            if len(batch) >= batch_size:
                self._seed_stock_for_products(batch, user)
                seeded += len(batch)
                self.stdout.write(f"  ... {seeded}/{total}", ending="\r")
                self.stdout.flush()
                batch = []

        if batch:
            self._seed_stock_for_products(batch, user)
            seeded += len(batch)

        stats = self._stock_stats()
        self.stdout.write(
            self.style.SUCCESS(
                f"\nStock seeded for {seeded} products. "
                f"Out of stock: {stats['out_of_stock']}, "
                f"low (1–{self._low_stock_max}): {stats['low_stock']}, "
                f"in stock (>{self._low_stock_max}): {stats['in_stock']}."
            )
        )

    def _stock_stats(self):
        annotated = Product.objects.annotate(stock=Sum("stock_movements__quantity"))
        out_of_stock = annotated.filter(stock__isnull=True).count() + annotated.filter(
            stock=0
        ).count()
        low_stock = annotated.filter(
            stock__gte=1,
            stock__lte=self._low_stock_max,
        ).count()
        in_stock = annotated.filter(stock__gt=self._low_stock_max).count()
        return {
            "out_of_stock": out_of_stock,
            "low_stock": low_stock,
            "in_stock": in_stock,
        }

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
