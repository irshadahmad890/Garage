from django.apps import apps
from apps.user.models import Role
from .models import Vehicle

def vehicles_for(user):
    """Which vehicles may this user see? Everything else is simply not found (404)."""
    qs = Vehicle.objects.select_related('customer')
    if user.role == Role.ADMIN:
        return qs
    if user.role == Role.CUSTOMER:
        return qs.filter(customer__user=user)
    if user.role == Role.MECHANIC:
        # only vehicles of jobs this mechanic is assigned to
        Job = apps.get_model('job', 'Job')
        return qs.filter(pk__in=Job.objects.filter(mechanic_assignments__mechanic__user=user).values('vehicle_id'))
    return qs.none()
