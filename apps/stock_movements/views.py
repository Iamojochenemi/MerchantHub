"""
API views for the ``stock_movements`` app.

Provides read-only access to the stock movement audit trail,
scoped to the authenticated user's active workspace.
"""

from rest_framework import generics, permissions

from apps.stock_movements.models import StockMovement
from apps.stock_movements.serializers import StockMovementSerializer
from apps.workspaces.utils import get_active_workspace


class StockMovementListView(generics.ListAPIView):
    """List stock movements for the authenticated user's workspace.

    **GET** ``/stock-movements/`` — Returns a paginated list of
    stock movements scoped to the user's active workspace, ordered
    newest first.
    """

    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return movements scoped to the user's workspace."""
        workspace = get_active_workspace(self.request)
        return StockMovement.objects.filter(
            inventory__product__workspace=workspace,
        ).select_related("inventory__product")


class StockMovementDetailView(generics.RetrieveAPIView):
    """Retrieve a single stock movement record.

    **GET** ``/stock-movements/<uuid>/`` — Returns the movement
    record.  Returns **404** if the record belongs to another
    workspace.
    """

    http_method_names = ["get", "head", "options"]
    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Scope to movements in the user's workspace."""
        workspace = get_active_workspace(self.request)
        return StockMovement.objects.filter(
            inventory__product__workspace=workspace,
        ).select_related("inventory__product")
