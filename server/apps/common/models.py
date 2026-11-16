from django.db import models


class DocumentSequence(models.Model):
    """One row per (document type, year). Locked while a number is handed out,
    so two requests can never get the same invoice / receipt number."""

    key = models.CharField(max_length=20)
    year = models.PositiveSmallIntegerField()
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["key", "year"], name="uniq_sequence_key_year")]
