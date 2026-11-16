from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.common.db import check_constraint


class Specialization(models.Model):

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Mechanic(models.Model):

    EXPERIENCE_LEVEL_CHOICES = [
        ('junior', 'Junior'),
        ('senior', 'Senior'),
        ('expert', 'Expert')
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='mechanic_profile')
    specialization = models.ForeignKey(Specialization, on_delete=models.PROTECT, related_name='mechanics')
    name = models.CharField(max_length=100)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVEL_CHOICES)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['id']
        constraints = [check_constraint(Q(hourly_rate__gte=0), 'mechanic_rate_non_negative')]


class JobMechanic(models.Model):

    # FIX: "job.Job" as a text. No import of the job app, so no circular import when job needs Mechanic.
    job = models.ForeignKey('job.Job', on_delete=models.CASCADE, related_name='mechanic_assignments')
    mechanic = models.ForeignKey(Mechanic, on_delete=models.PROTECT, related_name='job_assignments')
    working_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    # NEW: the rate is copied when the mechanic is assigned. A later raise does not change old invoices.
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    assigned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mechanic.name} - job {self.job_id}"

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'mechanic'],
                name='unique_job_mechanic'
            ),
            check_constraint(Q(working_hours__gte=0), 'jobmechanic_hours_non_negative'),
        ]
