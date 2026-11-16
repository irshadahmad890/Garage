from django.db import transaction
from rest_framework import generics

from apps.common.mixins import OwnerScopedQuerysetMixin
from apps.common.permissions import IsAdmin, IsAdminOrMechanicLimitedPatch, IsAdminOrMechanicReadOnly
from apps.user.models import Role

from .filters import JobMechanicFilter, MechanicFilter, SpecializationFilter
from .models import JobMechanic, Mechanic, Specialization
from .serializer import (
    JobMechanicHoursSerializer,
    JobMechanicSerializer,
    MechanicCreateSerializer,
    MechanicSerializer,
    SpecializationSerializer
)
# FIX: apps/mechanics/permissions.py is not needed any more. Delete it.


class SpecializationListCreateView(generics.ListCreateAPIView):
    queryset = Specialization.objects.all()
    serializer_class = SpecializationSerializer
    permission_classes = [IsAdmin]
    filterset_class = SpecializationFilter
    search_fields = ['name']


class SpecializationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Specialization.objects.all()
    serializer_class = SpecializationSerializer
    permission_classes = [IsAdmin]


class MechanicListCreateView(OwnerScopedQuerysetMixin, generics.ListCreateAPIView):
    """Admin: list all and create. Mechanic: read only, and only his own profile."""
    queryset = Mechanic.objects.select_related('user', 'specialization')
    owner_lookup = 'user'
    permission_classes = [IsAdminOrMechanicReadOnly]
    filterset_class = MechanicFilter
    search_fields = ['name', 'user__email', 'specialization__name']
    ordering_fields = ['name', 'hourly_rate', 'created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MechanicCreateSerializer
        return MechanicSerializer


class MechanicDetailView(OwnerScopedQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """FIX: a mechanic can read his profile but cannot change his rate, status or specialization."""
    queryset = Mechanic.objects.select_related('user', 'specialization')
    owner_lookup = 'user'
    serializer_class = MechanicSerializer
    permission_classes = [IsAdminOrMechanicReadOnly]

    @transaction.atomic
    def perform_destroy(self, instance):
        # A mechanic with assignments is protected (409). Deactivate him with is_active=false.
        user = instance.user
        instance.delete()
        user.delete()   # no orphan login account is left behind


# ---- Job Mechanic (assignments) ----

class _AssignmentMixin(OwnerScopedQuerysetMixin):
    queryset = JobMechanic.objects.select_related('job', 'mechanic', 'mechanic__user')
    owner_lookup = 'mechanic__user'
    permission_classes = [IsAdminOrMechanicLimitedPatch]

    def get_serializer_class(self):
        if self.request.user.role == Role.MECHANIC:
            return JobMechanicHoursSerializer
        return JobMechanicSerializer


class JobMechanicListCreateView(_AssignmentMixin, generics.ListCreateAPIView):
    filterset_class = JobMechanicFilter
    ordering_fields = ['assigned_at', 'working_hours']


class JobMechanicDetailView(_AssignmentMixin, generics.RetrieveUpdateDestroyAPIView):
    pass
