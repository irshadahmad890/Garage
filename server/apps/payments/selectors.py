from decimal import Decimal

from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.user.models import Role

from .models import Invoice, Payment

_MONEY = DecimalField(max_digits=14, decimal_places=2)


def with_paid_total(qs):
    """Amount paid as ONE sub-query, so a list of 100 invoices does not run 100 queries."""
    sub = Payment.objects.filter(invoice=OuterRef('pk')).order_by().values('invoice').annotate(t=Sum('amount')).values('t')
    return qs.annotate(paid_db=Coalesce(Subquery(sub, output_field=_MONEY), Value(Decimal('0.00'), output_field=_MONEY)))


def invoices_for(user):
    qs = with_paid_total(Invoice.objects.select_related('job__vehicle__customer'))
    if user.role == Role.ADMIN:
        return qs
    if user.role == Role.CUSTOMER:
        return qs.filter(job__vehicle__customer__user=user)   # own invoices only
    return qs.none()                                           # mechanics do not see money documents


def payments_for(user):
    qs = Payment.objects.select_related('invoice__job__vehicle__customer', 'received_by')
    if user.role == Role.ADMIN:
        return qs
    if user.role == Role.CUSTOMER:
        return qs.filter(invoice__job__vehicle__customer__user=user)
    return qs.none()
