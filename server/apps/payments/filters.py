import django_filters as filters
from django.utils import timezone

from .models import Invoice, InvoiceStatus, Payment, PaymentMethod


class InvoiceFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=InvoiceStatus.choices)
    job_number = filters.CharFilter(field_name='job__job_number', lookup_expr='icontains')
    customer = filters.NumberFilter(field_name='job__vehicle__customer_id')
    issued = filters.DateFromToRangeFilter(field_name='issued_at')    # ?issued_after=&issued_before=
    overdue = filters.BooleanFilter(method='filter_overdue')

    class Meta:
        model = Invoice
        fields = ['job']

    def filter_overdue(self, queryset, name, value):
        overdue = queryset.filter(due_date__lt=timezone.localdate()).exclude(status=InvoiceStatus.PAID)
        return overdue if value else queryset.exclude(pk__in=overdue.values('pk'))


class PaymentFilter(filters.FilterSet):
    method = filters.MultipleChoiceFilter(choices=PaymentMethod.choices)
    invoice_number = filters.CharFilter(field_name='invoice__invoice_number', lookup_expr='icontains')
    paid = filters.DateFromToRangeFilter(field_name='paid_at')
    min_amount = filters.NumberFilter(field_name='amount', lookup_expr='gte')

    class Meta:
        model = Payment
        fields = ['invoice']
