"""ONE place for role rules. Every app imports its permission classes from here.

  write_roles : these roles may use any method (GET, POST, PATCH, PUT, DELETE)
  read_roles  : these roles may only read (GET, HEAD, OPTIONS)
  patch_roles : these roles may read and PATCH (nothing else)

A new role later = add it to the right tuple in one class, here."""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.user.models import Role


class RolePermission(BasePermission):
    write_roles: tuple = ()
    read_roles: tuple = ()
    patch_roles: tuple = ()

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        role = user.role
        if role in self.write_roles:
            return True
        if request.method in SAFE_METHODS:
            return role in self.read_roles
        if request.method == "PATCH":
            return role in self.patch_roles
        return False


class IsAdmin(RolePermission):
    write_roles = (Role.ADMIN,)


class IsCustomer(RolePermission):
    write_roles = (Role.CUSTOMER,)


class IsMechanic(RolePermission):
    write_roles = (Role.MECHANIC,)


class IsAdminOrCustomer(RolePermission):
    write_roles = (Role.ADMIN, Role.CUSTOMER)


class IsAdminOrMechanicReadOnly(RolePermission):
    write_roles = (Role.ADMIN,)
    read_roles = (Role.MECHANIC,)


class IsAdminCustomerOrMechanicReadOnly(RolePermission):
    write_roles = (Role.ADMIN, Role.CUSTOMER)
    read_roles = (Role.MECHANIC,)


class IsAdminOrMechanicLimitedPatch(RolePermission):
    """Admin: everything. Mechanic: read and PATCH (the serializer limits which fields)."""
    write_roles = (Role.ADMIN,)
    read_roles = (Role.MECHANIC,)
    patch_roles = (Role.MECHANIC,)
