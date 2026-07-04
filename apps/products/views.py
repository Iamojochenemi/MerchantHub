"""
API views for the ``products`` app.

Keeps views thin: validation is handled by ``ProductSerializer``
and business logic is delegated to ``ProductService``.
"""

from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.products.models import Product
from apps.products.serializers import ProductSerializer
from apps.products.services import ProductService
from apps.workspaces.utils import get_active_workspace


class ProductListCreateView(generics.ListCreateAPIView):
    """List all active products in the workspace, or create a new one.

    **GET** ``/products/`` — Returns a paginated list of active products
    belonging to the authenticated user's workspace.

    **POST** ``/products/`` — Create a new product. The ``workspace`` is
    resolved from the authenticated user's active workspace membership;
    clients must not provide it in the request body.
    """

    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only active products scoped to the user's workspace."""
        workspace = get_active_workspace(self.request)
        return Product.objects.filter(
            workspace=workspace,
            is_active=True,
        )


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or soft-delete (archive) a product.

    **GET** ``/products/<uuid>/`` — Returns the product details.

    **PATCH** ``/products/<uuid>/`` — Partial update of the product.

    **DELETE** ``/products/<uuid>/`` — Archives the product by setting
    ``is_active`` to ``False`` (soft delete). Products are never
    hard-deleted through the API.

    Returns **404** if the product does not exist or belongs to a
    different workspace.
    """

    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Scope to active products in the user's workspace.

        Because ``get_object()`` calls ``filter_queryset()`` on this
        queryset, products in other workspaces or inactive products
        will naturally return **404**.
        """
        workspace = get_active_workspace(self.request)
        return Product.objects.filter(
            workspace=workspace,
            is_active=True,
        )

    def perform_destroy(self, instance: Product) -> None:
        """Soft-delete the product instead of removing it from the DB."""
        ProductService.archive_product(instance=instance)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """Return 200 OK with the archived product data on soft delete."""
        instance = self.get_object()
        self.perform_destroy(instance)
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)
