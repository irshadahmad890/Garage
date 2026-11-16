from apps.user.models import Role


class OwnerScopedQuerysetMixin:
    """Row-level security in one place. Admin sees every row; any other role sees
    only the rows linked to the logged-in user. Others' rows are a 404, not a 403."""

    owner_lookup: str = ""  # example: "customer__user"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Role.ADMIN:
            return qs
        return qs.filter(**{self.owner_lookup: user})
