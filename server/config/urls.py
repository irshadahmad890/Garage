from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.user.urls")),
    path("api/customers/", include("apps.customers.urls")),
    path("api/vehicles/", include("apps.vehicle.urls")),
    path("api/mechanics/", include("apps.mechanics.urls")),
    path("api/parts/", include("apps.parts.urls")),
    path("api/payments/", include("apps.payments.urls")),
]
