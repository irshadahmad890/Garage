import re
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.customers.models import Customer


def normalize_plate(value):
    """'lea-123', 'LEA 123' and 'Lea123' are the SAME plate: LEA123."""
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def validate_model_year(value):
    if value > date.today().year + 1:          # FIX: was a fixed 2100
        raise ValidationError("The model year cannot be in the far future.")


class Vehicle(models.Model):

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='vehicles')
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.PositiveIntegerField(validators=[MinValueValidator(1900), validate_model_year])
    registration_number = models.CharField(max_length=20, unique=True)
    vin = models.CharField(max_length=17, unique=True, null=True, blank=True)   # NEW
    odometer_km = models.PositiveIntegerField(default=0)                          # NEW
    is_active = models.BooleanField(default=True)                                 # NEW
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.registration_number = normalize_plate(self.registration_number)
        self.vin = (self.vin or "").strip().upper() or None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.make} {self.model} - {self.registration_number}"

    class Meta:
        ordering = ['-created_at', '-id']
