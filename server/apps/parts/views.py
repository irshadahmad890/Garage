from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView
)

from apps.common.mixins import OwnerScopedQuerysetMixin
from apps.common.permissions import IsAdminOrMechanicReadOnly

from .filters import JobPartFilter, PartFilter
from .models import JobPart, Part
from .serializer import JobPartSerializer, PartSerializer

# FIX (critical): the part views had NO permission_classes, so a customer, or an anonymous user
# when the default is AllowAny, could create, change and delete parts. Now: admin writes, mechanic reads.


class PartListCreateView(ListCreateAPIView):
    queryset = Part.objects.all()
    serializer_class = PartSerializer
    permission_classes = [IsAdminOrMechanicReadOnly]
    filterset_class = PartFilter
    search_fields = ['name']
    ordering_fields = ['name', 'price', 'stock']


class PartDetailView(RetrieveUpdateDestroyAPIView):
    """A part that is used in a job cannot be deleted (409). Set is_active to false instead."""
    queryset = Part.objects.all()
    serializer_class = PartSerializer
    permission_classes = [IsAdminOrMechanicReadOnly]


class _JobPartMixin(OwnerScopedQuerysetMixin):
    """NEW endpoints for JobPart. Admin: everything. Mechanic: read the parts of his own jobs."""
    queryset = JobPart.objects.select_related('part')
    owner_lookup = 'job__mechanic_assignments__mechanic__user'
    serializer_class = JobPartSerializer
    permission_classes = [IsAdminOrMechanicReadOnly]


class JobPartListCreateView(_JobPartMixin, ListCreateAPIView):
    filterset_class = JobPartFilter


class JobPartDetailView(_JobPartMixin, RetrieveUpdateDestroyAPIView):
    pass
