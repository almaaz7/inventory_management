from rest_framework import serializers
from .models import *

class CategorySerializer(serializers.ModelSerializer):

    breadcrumb = serializers.SerializerMethodField()
    class Meta:
        model = Category
        fields = ['name', 'slug', 'parent', 'breadcrumb']

    def get_breadcrumb(self, obj):
        trail = []
        current = obj

        while current is not None:
            trail.append(current.name)
            current = current.parent
        
        return ' > '.join(trail[::-1])

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['name', 'email', 'lead_time_days']

class ProductSerializer(serializers.ModelSerializer):

    category_name = serializers.CharField(source='category.name', read_only=True)

    current_stock = serializers.IntegerField(source='calculated_stock', read_only=True)

    suppliers = serializers.SlugRelatedField(many=True, read_only=True, slug_field='name', source='supplier')

    class Meta:
        model = Product
        fields = ['name', 'sku', 'description', 'price', 'category_name', 'current_stock', 'suppliers', 'category', 'supplier']

class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = ['product', 'quantity', 'reason']