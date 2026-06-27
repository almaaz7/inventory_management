from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated

from .permissions import IsManager, IsStaff
from .models import Category, Supplier, Product, StockMovement
from .serializers import CategorySerializer, SupplierSerializer, ProductSerializer, StockMovementSerializer

# Create your views here.
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
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'update', 'partial_update']:
            permission_classes = [IsAuthenticated, IsManager | IsStaff]
        else:
            permission_classes = [IsAuthenticated, IsManager]
        
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        return Product.objects.select_related('category').prefetch_related('supplier').annotate(
            calculated_stock = Coalesce(Sum('stock_movements__quantity'), 0)
        )

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
        serializer.save(created_by = self.request.user)