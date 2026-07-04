"""URL configuration for the ``inventory`` app."""

from django.urls import path

from apps.inventory.views import InventoryDetailView, InventoryListView

app_name = "inventory"

urlpatterns = [
    path("inventory/", InventoryListView.as_view(), name="inventory-list"),
    path(
        "inventory/<uuid:pk>/",
        InventoryDetailView.as_view(),
        name="inventory-detail",
    ),
]
