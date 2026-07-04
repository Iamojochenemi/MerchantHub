"""
API views for the ``sales`` app.

Keeps views thin: validation is handled by ``SaleSerializer``
and business logic is delegated to ``SalesService``.
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.sales.models import Sale
from apps.sales.serializers import SaleSerializer
from apps.workspaces.utils import get_active_workspace


class SaleListCreateView(generics.ListCreateAPIView):
    """List sales or create a new sale.

    **GET** ``/sales/`` — Returns a paginated list of sales
    belonging to the authenticated user's active workspace,
    ordered newest first.

    **POST** ``/sales/`` — Creates a new sale.  ``workspace`` and
    ``created_by`` are resolved from the authenticated request;
    clients must not provide them.
    """

    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return sales scoped to the user's workspace, newest first."""
        workspace = get_active_workspace(self.request)
        return Sale.objects.filter(workspace=workspace)

    def create(self, request, *args, **kwargs):
        """Create a sale and return HTTP 201 with the serialised sale."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = serializer.save()
        output = SaleSerializer(sale, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class SaleDetailView(generics.RetrieveAPIView):
    """Retrieve a single sale.

    **GET** ``/sales/<uuid>/`` — Returns the sale details including
    line items.  Returns **404** if the sale belongs to another workspace.
    """

    http_method_names = ["get", "head", "options"]
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Scope to sales in the user's workspace.

        Because ``get_object()`` calls ``filter_queryset()`` on this
        queryset, sales in other workspaces naturally return **404**.
        """
        workspace = get_active_workspace(self.request)
        return Sale.objects.filter(workspace=workspace)
