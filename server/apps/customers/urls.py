from django.urls import path
from . import views

urlpatterns = [
    path("", views.CustomerListCreateView.as_view(), name='customers'),
    path("me/", views.MyCustomerProfileView.as_view(), name='customer_me'),   # must stay above <int:pk>/
    path("<int:pk>/", views.CustomerDetailView.as_view(), name="customer_detail"),
]
