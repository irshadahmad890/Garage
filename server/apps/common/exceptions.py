from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class Conflict(APIException):
    """409: the request is valid, but it clashes with the current data."""

    status_code = 409
    default_detail = "The request conflicts with the current state of the data."
    default_code = "conflict"


def api_exception_handler(exc, context):
    """Turns database errors into clean API answers instead of HTTP 500."""
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(detail=exc.message_dict if hasattr(exc, "error_dict") else exc.messages)
    elif isinstance(exc, ProtectedError):
        exc = Conflict("This record is used by other records, so it cannot be deleted. "
                       "Deactivate it instead (set is_active to false).")
    elif isinstance(exc, IntegrityError):
        exc = Conflict("A record with the same unique value already exists.")
    return exception_handler(exc, context)
