"""STUB. This is NOT your real job app. It exists only so the other apps and the tests can run.
Keep your own apps/job. The other apps need only these things from Job:
job_number, vehicle (FK), status."""
from django.db import models

from apps.common.numbering import next_number


class Job(models.Model):
    job_number = models.CharField(max_length=20, unique=True, blank=True)
    vehicle = models.ForeignKey("vehicle.Vehicle", on_delete=models.PROTECT, related_name="jobs")
    status = models.CharField(max_length=20, default="DRAFT")
    complaint = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.job_number:
            self.job_number = next_number("job", "JC")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.job_number
