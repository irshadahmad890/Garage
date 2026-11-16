import django_filters as filters
from django.db.models import F, Q

from .models import JobPart, Part


class PartFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr='icontains')
    min_price = filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = filters.NumberFilter(field_name='price', lookup_expr='lte')
    low_stock = filters.BooleanFilter(method='filter_low_stock')   # stock <= reorder_level

    class Meta:
        model = Part
        fields = ['is_active']

    def filter_low_stock(self, queryset, name, value):
        condition = Q(stock__lte=F('reorder_level'))
        return queryset.filter(condition) if value else queryset.exclude(condition)


class JobPartFilter(filters.FilterSet):
    class Meta:
        model = JobPart
        fields = ['job', 'part']
