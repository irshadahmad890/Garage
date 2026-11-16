import django_filters as filters

from .models import Vehicle, normalize_plate


class VehicleFilter(filters.FilterSet):
    plate = filters.CharFilter(method='filter_plate')
    make = filters.CharFilter(lookup_expr='icontains')
    year = filters.RangeFilter()   # ?year_min=2015&year_max=2020

    class Meta:
        model = Vehicle
        fields = ['customer', 'is_active']

    def filter_plate(self, queryset, name, value):
        return queryset.filter(registration_number__icontains=normalize_plate(value))
