from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from apps.common.db import check_constraint


class InvoiceStatus(models.TextChoices):
    ISSUED = "ISSUED", "Issued"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    PAID = "PAID", "Paid"


class Invoice(models.Model):
    """One invoice per job. The amounts are copied (snapshot) when the invoice is made,
    so a later change of a part price or a mechanic rate can never change an issued invoice."""

    job = models.OneToOneField('job.Job', on_delete=models.PROTECT, related_name='invoice')
    invoice_number = models.CharField(max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.ISSUED, db_index=True)
    parts_total = models.DecimalField(max_digits=12, decimal_places=2)
    labor_total = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    issued_at = models.DateTimeField(default=timezone.now, db_index=True)
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issued_at', '-id']
        constraints = [
            check_constraint(Q(discount__gte=0), 'invoice_discount_non_negative'),
            check_constraint(Q(total__gte=0), 'invoice_total_non_negative'),
        ]

    @property
    def amount_paid(self):
        value = getattr(self, 'paid_db', None)   # filled by selectors.with_paid_total(): no extra query
        if value is None:
            value = self.payments.aggregate(t=Sum('amount'))['t']
        return Decimal(value or 0).quantize(Decimal('0.01'))

    @property
    def balance_due(self):
        return (self.total - self.amount_paid).quantize(Decimal('0.01'))

    def __str__(self):
        return self.invoice_number


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    CARD = "card", "Card"
    BANK_TRANSFER = "bank_transfer", "Bank transfer"
    MOBILE_WALLET = "mobile_wallet", "Mobile wallet"


class Payment(models.Model):
    """A payment is also the digital receipt. Receipt numbers are unique and in sequence."""

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    receipt_number = models.CharField(max_length=20, unique=True, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(default=timezone.now, db_index=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_at', '-id']
        constraints = [check_constraint(Q(amount__gt=0), 'payment_amount_positive')]

    def __str__(self):
        return self.receipt_number
