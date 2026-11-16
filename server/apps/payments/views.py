from django.apps import apps
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdmin, IsAdminOrCustomer

from . import services
from .filters import InvoiceFilter, PaymentFilter
from .rendering import render_document
from .selectors import invoices_for, payments_for, with_paid_total
from .serializer import (
    GenerateInvoiceSerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    PaymentSerializer,
    RecordPaymentSerializer
)
from .models import Invoice

# Admin: all invoices and payments. Customer: only their own (read only). Mechanic: none (403).


class InvoiceListView(generics.ListAPIView):
    serializer_class = InvoiceListSerializer
    permission_classes = [IsAdminOrCustomer]
    filterset_class = InvoiceFilter
    search_fields = ['invoice_number', 'job__job_number', 'job__vehicle__registration_number',
                     'job__vehicle__customer__name']
    ordering_fields = ['issued_at', 'total', 'due_date']

    def get_queryset(self):
        return invoices_for(self.request.user)


class InvoiceDetailView(generics.RetrieveAPIView):
    serializer_class = InvoiceDetailSerializer
    permission_classes = [IsAdminOrCustomer]

    def get_queryset(self):
        return invoices_for(self.request.user).prefetch_related('payments__received_by')


class InvoicePrintView(APIView):
    permission_classes = [IsAdminOrCustomer]

    def get(self, request, pk):
        invoice = get_object_or_404(invoices_for(request.user), pk=pk)
        return render_document(request, invoice)


class RecordPaymentView(APIView):
    """POST /invoices/<id>/payments/ (admin). Partial or full. A full payment fires the invoice_paid signal."""
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        invoice = get_object_or_404(invoices_for(request.user), pk=pk)
        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = services.record_payment(invoice.pk, received_by=request.user, **serializer.validated_data)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class GenerateInvoiceView(APIView):
    """POST /jobs/<job_id>/generate-invoice/ (admin). The job must have an invoiceable status."""
    permission_classes = [IsAdmin]

    def post(self, request, job_pk):
        job = get_object_or_404(apps.get_model('job', 'Job'), pk=job_pk)
        serializer = GenerateInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = services.generate_invoice(job.pk, issued_by=request.user, **serializer.validated_data)
        invoice = with_paid_total(Invoice.objects.select_related('job__vehicle__customer')).get(pk=invoice.pk)
        return Response(InvoiceDetailSerializer(invoice, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)


class PaymentListView(generics.ListAPIView):
    """Receipts."""
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminOrCustomer]
    filterset_class = PaymentFilter
    search_fields = ['receipt_number', 'reference', 'invoice__invoice_number']
    ordering_fields = ['paid_at', 'amount']

    def get_queryset(self):
        return payments_for(self.request.user)


class PaymentDetailView(generics.RetrieveAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminOrCustomer]

    def get_queryset(self):
        return payments_for(self.request.user)


class ReceiptPrintView(APIView):
    permission_classes = [IsAdminOrCustomer]

    def get(self, request, pk):
        payment = get_object_or_404(payments_for(request.user), pk=pk)
        return render_document(request, payment.invoice, payment=payment)
