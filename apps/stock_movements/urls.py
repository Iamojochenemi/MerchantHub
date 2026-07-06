"""URL configuration for the ``stock_movements`` app."""

from django.urls import path

from apps.stock_movements.views import (
    StockMovementDetailView,
    StockMovementListView,
)

app_name = "stock_movements"

urlpatterns = [
    path(
        "stock-movements/",
        StockMovementListView.as_view(),
        name="stockmovement-list",
    ),
    path(
        "stock-movements/<uuid:pk>/",
        StockMovementDetailView.as_view(),
        name="stockmovement-detail",
    ),
]
