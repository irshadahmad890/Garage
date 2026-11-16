from django.db import transaction
from django.utils import timezone

from .models import DocumentSequence


@transaction.atomic
def next_number(key: str, prefix: str, width: int = 5) -> str:
    """Returns e.g. INV-2026-00042 (row lock on MySQL / Postgres)."""
    year = timezone.localdate().year
    seq, _ = DocumentSequence.objects.select_for_update().get_or_create(key=key, year=year)
    seq.last_value += 1
    seq.save(update_fields=["last_value"])
    return f"{prefix}-{year}-{seq.last_value:0{width}d}"
