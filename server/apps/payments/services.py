from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import DecimalField, F, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.common.exceptions import Conflict
from apps.common.numbering import next_number
from apps.mechanics.models import JobMechanic
from apps.parts.models import JobPart

from .models import Invoice, InvoiceStatus, Payment
from .signals import invoice_paid

TWO = Decimal('0.01')
MONEY = DecimalField(max_digits=14, decimal_places=2)

# An invoice can be made only when the job has one of these statuses.
# CHANGE THIS to match the status values of YOUR job app.
INVOICEABLE_STATUSES = ('COMPLETED',)


def job_totals(job):
    parts = JobPart.objects.filter(job=job).aggregate(
        t=Sum(F('quantity') * F('unit_price'), output_field=MONEY))['t'] or Decimal('0')
    labor = JobMechanic.objects.filter(job=job).aggregate(
        t=Sum(F('working_hours') * F('hourly_rate'), output_field=MONEY))['t'] or Decimal('0')
    return Decimal(parts).quantize(TWO), Decimal(labor).quantize(TWO)


def invoice_lines(job):
    """Parts lines and labor lines, for the API answer and for the printable page."""
    lines = []
    for jp in JobPart.objects.filter(job=job).select_related('part').order_by('id'):
        lines.append({'type': 'Part', 'description': jp.part.name, 'quantity': jp.quantity,
                      'unit_price': jp.unit_price, 'line_total': jp.line_total})
    for jm in JobMechanic.objects.filter(job=job).select_related('mechanic').order_by('id'):
        lines.append({'type': 'Labor', 'description': f'Labor - {jm.mechanic.name} (hours)',
                      'quantity': jm.working_hours, 'unit_price': jm.hourly_rate,
                      'line_total': (jm.working_hours * jm.hourly_rate).quantize(TWO)})
    return lines


@transaction.atomic
def generate_invoice(job_id, *, issued_by, discount=Decimal('0'), tax_percent=None) -> Invoice:
    Job = apps.get_model('job', 'Job')
    job = Job.objects.select_for_update().get(pk=job_id)
    if job.status not in INVOICEABLE_STATUSES:
        raise Conflict(f'An invoice can only be made for a job with status {", ".join(INVOICEABLE_STATUSES)}.')
    if Invoice.objects.filter(job=job).exists():
        raise Conflict('This job already has an invoice.')
    parts_total, labor_total = job_totals(job)
    subtotal = parts_total + labor_total
    discount = Decimal(discount).quantize(TWO)
    if discount > subtotal:
        raise ValidationError({'discount': 'The discount cannot be bigger than the subtotal.'})
    tax_percent = Decimal(settings.DEFAULT_TAX_PERCENT if tax_percent is None else tax_percent).quantize(TWO)
    tax_amount = ((subtotal - discount) * tax_percent / 100).quantize(TWO)
    return Invoice.objects.create(
        job=job, invoice_number=next_number('invoice', 'INV'), parts_total=parts_total, labor_total=labor_total,
        subtotal=subtotal, discount=discount, tax_percent=tax_percent, tax_amount=tax_amount,
        total=subtotal - discount + tax_amount,
        due_date=timezone.localdate() + timedelta(days=settings.INVOICE_DUE_DAYS), issued_by=issued_by)


@transaction.atomic
def record_payment(invoice_id, *, amount, method, reference, received_by) -> Payment:
    invoice = Invoice.objects.select_for_update().get(pk=invoice_id)   # two payments at once are handled one by one
    if invoice.status == InvoiceStatus.PAID:
        raise Conflict('This invoice is already fully paid.')
    paid = invoice.payments.aggregate(t=Sum('amount'))['t'] or Decimal('0')
    balance = invoice.total - paid
    if amount > balance:
        raise ValidationError({'amount': f'The amount is more than the balance due ({balance}).'})
    payment = Payment.objects.create(invoice=invoice, amount=amount, method=method, reference=reference,
                                     received_by=received_by, receipt_number=next_number('receipt', 'RCT'))
    fully_paid = paid + amount >= invoice.total
    invoice.status = InvoiceStatus.PAID if fully_paid else InvoiceStatus.PARTIALLY_PAID
    if fully_paid:
        invoice.paid_at = timezone.now()
    invoice.save()
    if fully_paid:
        invoice_paid.send(sender=Invoice, invoice=invoice)
    return payment
