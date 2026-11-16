from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateAPIView,
    RetrieveUpdateDestroyAPIView
)

from apps.common.permissions import IsAdmin, IsCustomer
from .filters import CustomerFilter
from .models import Customer
from .serializer import CustomerSelfSerializer, CustomerSerializer


class CustomerListCreateView(ListCreateAPIView):
    """Admin only. Staff creates walk-in customers here.
    FIX: perform_create no longer links the new customer to whoever calls the API."""
    queryset = Customer.objects.annotate(vehicle_count=Count('vehicles', distinct=True)).order_by('-created_at', '-id')
    serializer_class = CustomerSerializer
    permission_classes = [IsAdmin]
    filterset_class = CustomerFilter
    search_fields = ['name', 'phone', 'address', 'user__email']
    ordering_fields = ['name', 'created_at']


class CustomerDetailView(RetrieveUpdateDestroyAPIView):
    """Admin only. A customer that still owns vehicles cannot be deleted (409): deactivate it."""
    queryset = Customer.objects.annotate(vehicle_count=Count('vehicles', distinct=True))
    serializer_class = CustomerSerializer
    permission_classes = [IsAdmin]


class MyCustomerProfileView(RetrieveUpdateAPIView):
    """NEW. The logged-in customer reads and edits only their own profile. No ID in the URL."""
    serializer_class = CustomerSelfSerializer
    permission_classes = [IsCustomer]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return get_object_or_404(Customer, user=self.request.user)
