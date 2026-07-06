"""URL configuration for the ``customers`` app."""

from django.urls import path

from apps.customers.views import CustomerDetailView, CustomerListCreateView

app_name = "customers"

urlpatterns = [
    path("customers/", CustomerListCreateView.as_view(), name="customer-list"),
    path(
        "customers/<uuid:pk>/",
        CustomerDetailView.as_view(),
        name="customer-detail",
    ),
]
