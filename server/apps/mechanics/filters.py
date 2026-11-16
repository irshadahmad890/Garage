import django_filters as filters

from .models import JobMechanic, Mechanic, Specialization


class SpecializationFilter(filters.FilterSet):
    class Meta:
        model = Specialization
        fields = ['is_active']


class MechanicFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Mechanic
        fields = ['specialization', 'experience_level', 'is_active']


class JobMechanicFilter(filters.FilterSet):
    class Meta:
        model = JobMechanic
        fields = ['job', 'mechanic']
