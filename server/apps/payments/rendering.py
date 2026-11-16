from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string

from .services import invoice_lines


def render_document(request, invoice, payment=None):
    """Printable page (invoice or receipt). The page has print CSS: Print -> Save as PDF."""
    job = invoice.job
    html = render_to_string('payments/document.html', {
        'mode': 'receipt' if payment else 'invoice',
        'invoice': invoice, 'payment': payment, 'job': job, 'vehicle': job.vehicle,
        'customer': job.vehicle.customer, 'items': invoice_lines(job),
        'payments': invoice.payments.order_by('paid_at', 'id'),
        'shop': {'name': settings.SHOP_NAME, 'address': settings.SHOP_ADDRESS, 'phone': settings.SHOP_PHONE},
        'currency': settings.CURRENCY,
    }, request=request)
    response = HttpResponse(html, content_type='text/html; charset=utf-8')
    response['Cache-Control'] = 'private, no-store'
    return response
