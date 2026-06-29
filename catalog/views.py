from django.conf import settings
from django.core.cache import cache
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .cache_utils import invalidate_product_list_cache, product_list_cache_key
from .stock import recompute_product_stock
from .tasks import notify_supplier
from .filters import ProductFilter
from .permissions import IsManager, IsStaff
from .models import Category, Supplier, Product, StockMovement
from .serializers import CategorySerializer, SupplierSerializer, ProductSerializer, StockMovementSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsManager]


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, IsManager]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'sku']
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated, IsManager | IsStaff]
        else:
            permission_classes = [IsAuthenticated, IsManager]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        return Product.objects.select_related('category').prefetch_related('supplier')

    def list(self, request, *args, **kwargs):
        cache_key = product_list_cache_key(request)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=settings.PRODUCT_LIST_CACHE_TTL)
        return response

    def perform_create(self, serializer):
        serializer.save()
        invalidate_product_list_cache()

    def perform_update(self, serializer):
        serializer.save()
        invalidate_product_list_cache()

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_product_list_cache()


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'create', 'update']:
            permission_classes = [IsAuthenticated, IsManager | IsStaff]
        else:
            permission_classes = [IsAuthenticated, IsManager]

        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        movement = serializer.save(created_by=self.request.user)
        product = movement.product
        product.current_stock = max(0, product.current_stock + movement.quantity)
        product.save(update_fields=['current_stock'])
        invalidate_product_list_cache()
        notify_supplier.delay(movement.product_id, movement.id, threshold=20)

    def perform_update(self, serializer):
        old_product_id = serializer.instance.product_id
        movement = serializer.save()
        recompute_product_stock(old_product_id)
        if movement.product_id != old_product_id:
            recompute_product_stock(movement.product_id)
        invalidate_product_list_cache()

    def perform_destroy(self, instance):
        product_id = instance.product_id
        instance.delete()
        recompute_product_stock(product_id)
        invalidate_product_list_cache()
