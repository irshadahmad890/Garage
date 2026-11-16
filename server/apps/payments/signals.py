from django.dispatch import Signal

# Sent when an invoice becomes fully paid. The job app listens to this and closes the job:
#   @receiver(invoice_paid)
#   def close_job(sender, invoice, **kwargs): ...
# So payments never needs to know how your job stages work.
invoice_paid = Signal()
