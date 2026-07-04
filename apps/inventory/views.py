"""
API views for the ``inventory`` app.

Keeps views thin: serialization is handled by ``InventorySerializer``
and stock mutations are delegated to ``InventoryService``.
"""

from rest_framework import generics, permissions
from rest_framework.response import Response

from apps.inventory.models import Inventory
from apps.inventory.serializers import InventorySerializer
from apps.workspaces.utils import get_active_workspace


class InventoryListView(generics.ListAPIView):
    """List inventory records for the authenticated user's workspace.

    **GET** ``/inventory/`` — Returns a paginated list of inventory
    records scoped to the authenticated user's active workspace.
    Only products with an inventory record are shown.
    """

    serializer_class = InventorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return inventory records scoped to the user's workspace."""
        workspace = get_active_workspace(self.request)
        return Inventory.objects.filter(
            product__workspace=workspace,
        ).select_related("product")


class InventoryDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or adjust the quantity of an inventory record.

    **GET** ``/inventory/<uuid>/`` — Returns the inventory record.

    **PATCH** ``/inventory/<uuid>/`` — Adjusts the stock quantity.
    Only the ``quantity`` field may be updated.

    No **DELETE** or **PUT** methods are exposed.
    """

    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = InventorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Scope to inventory records in the user's workspace."""
        workspace = get_active_workspace(self.request)
        return Inventory.objects.filter(
            product__workspace=workspace,
        ).select_related("product")
