from time import timezone
from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.save()

    def __str__(self):
        return self.name

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    lead_time_days = models.PositiveIntegerField(
        default=0,
        help_text="Average number of days for delivery after an order is placed"
    )

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products'
    )

    supplier = models.ManyToManyField(
        Supplier,
        related_name='products'
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['category', 'is_active']),
        ]

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.save()

    def __str__(self):
        return self.name

    @property
    def current_stock(self):
        result = self.stock_movements.aggregate(total=models.Sum('quantity'))['total']
        return result if result is not None else 0

class StockMovement(models.Model):

    REASON_RECEIVED = 'received' 
    REASON_SOLD = 'sold'
    REASON_ADJUSTED = 'adjusted'

    REASON_CHOICES = [
        (REASON_RECEIVED, 'Received'),
        (REASON_SOLD, 'Sold'),
        (REASON_ADJUSTED, 'Adjusted')
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )

    quantity = models.IntegerField()

    reason = models.CharField(
        max_length = 20,
        choices=REASON_CHOICES
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='inventory_actions'
    )

    def __str__(self):
        return f"{self.product.name} - {self.quantity:+} by {self.created_by.username}"