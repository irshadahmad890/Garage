from decimal import Decimal

from rest_framework import serializers

from .models import Invoice, Payment, PaymentMethod
from .services import invoice_lines


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    received_by_name = serializers.CharField(source='received_by.username', read_only=True, default=None)

    class Meta:
        model = Payment
        fields = ['id', 'receipt_number', 'invoice', 'invoice_number', 'amount', 'method', 'reference',
                  'paid_at', 'received_by_name']


class InvoiceListSerializer(serializers.ModelSerializer):
    job_number = serializers.CharField(source='job.job_number', read_only=True)
    registration_number = serializers.CharField(source='job.vehicle.registration_number', read_only=True)
    customer_name = serializers.CharField(source='job.vehicle.customer.name', read_only=True)
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'invoice_number', 'job', 'job_number', 'registration_number', 'customer_name', 'status',
                  'parts_total', 'labor_total', 'subtotal', 'discount', 'tax_percent', 'tax_amount', 'total',
                  'amount_paid', 'balance_due', 'issued_at', 'due_date', 'paid_at']


class InvoiceDetailSerializer(InvoiceListSerializer):
    lines = serializers.SerializerMethodField()
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + ['lines', 'payments']

    def get_lines(self, invoice):
        return [{**line, 'unit_price': str(line['unit_price']), 'line_total': str(line['line_total']),
                 'quantity': str(line['quantity'])} for line in invoice_lines(invoice.job)]


class GenerateInvoiceSerializer(serializers.Serializer):
    discount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'), default=Decimal('0'))
    tax_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'),
                                           max_value=Decimal('100'), required=False)


class RecordPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=100, default='')
