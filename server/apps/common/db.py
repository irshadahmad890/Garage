import django
from django.db import models


def check_constraint(condition, name):
    """CheckConstraint works on every Django version (the argument was renamed in 5.1)."""
    key = "condition" if django.VERSION >= (5, 1) else "check"
    return models.CheckConstraint(**{key: condition}, name=name)
