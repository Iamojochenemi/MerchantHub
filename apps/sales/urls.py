"""URL configuration for the ``sales`` app."""

from django.urls import path

from apps.sales.views import SaleDetailView, SaleListCreateView

app_name = "sales"

urlpatterns = [
    path("sales/", SaleListCreateView.as_view(), name="sale-list"),
    path(
        "sales/<uuid:pk>/",
        SaleDetailView.as_view(),
        name="sale-detail",
    ),
]
