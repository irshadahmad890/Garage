from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView

from apps.common.permissions import IsAdmin, IsAdminCustomerOrMechanicReadOnly
from apps.user.models import Role

from .filters import VehicleFilter
from .selectors import vehicles_for
from .serializer import VehicleAdminSerializer, VehicleCustomerSerializer


class _SerializerByRoleMixin:
    def get_serializer_class(self):
        if self.request.user.role == Role.CUSTOMER:
            return VehicleCustomerSerializer
        return VehicleAdminSerializer


class VehicleListCreateView(_SerializerByRoleMixin, ListCreateAPIView):
    permission_classes = [IsAdminCustomerOrMechanicReadOnly]
    filterset_class = VehicleFilter
    search_fields = ['registration_number', 'vin', 'make', 'model', 'customer__name']
    ordering_fields = ['registration_number', 'year', 'created_at']

    def get_queryset(self):
        return vehicles_for(self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == Role.CUSTOMER:
            profile = getattr(user, 'customer_profile', None)
            if profile is None or not profile.is_active:
                raise ValidationError("Your customer profile is missing or inactive. Please contact the garage.")
            serializer.save(customer=profile)   # ownership comes from the login
        else:
            serializer.save()


class VehicleDetailView(_SerializerByRoleMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminCustomerOrMechanicReadOnly]

    def get_permissions(self):
        # FIX: a customer could delete a vehicle (and its service history). Only admin can.
        if self.request.method == 'DELETE':
            return [IsAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        return vehicles_for(self.request.user)
