from django.urls import path
from .views import (PartListCreateView,
                    PartDetailView,
                    JobPartListCreateView,
                    JobPartDetailView)

urlpatterns = [
    path("", PartListCreateView.as_view(), name="part_list_add"),
    path("<int:pk>/", PartDetailView.as_view(), name="parts_update"),
    path("job-parts/", JobPartListCreateView.as_view(), name="job_part_list_add"),
    path("job-parts/<int:pk>/", JobPartDetailView.as_view(), name="job_part_detail"),
]
