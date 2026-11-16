from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.common.db import check_constraint


class Part(models.Model):

    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])  # FIX: was no limit
    stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=5)    # NEW: for the low-stock filter
    is_active = models.BooleanField(default=True)              # NEW: stop selling a part without deleting it
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        constraints = [check_constraint(Q(price__gte=0), 'part_price_non_negative')]


class JobPart(models.Model):

    job = models.ForeignKey('job.Job', on_delete=models.CASCADE, related_name='used_parts')   # FIX: text reference
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name='job_usages')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)   # snapshot, copied from Part.price

    @property
    def line_total(self):
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.part.name} - {self.quantity}"

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'part'],
                name='unique_job_part'
            ),
            check_constraint(Q(unit_price__gte=0), 'jobpart_price_non_negative'),
        ]
