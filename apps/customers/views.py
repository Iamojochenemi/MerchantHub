"""
API views for the ``customers`` app.

Keeps views thin: validation is handled by ``CustomerSerializer``
and business logic is delegated to ``CustomerService``.
"""

from rest_framework import generics, permissions
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.customers.models import Customer
from apps.customers.serializers import CustomerSerializer
from apps.workspaces.utils import get_active_workspace


class CustomerListCreateView(generics.ListCreateAPIView):
    """List all customers in the workspace, or create a new one.

    **GET** ``/customers/`` — Returns a paginated list of customers
    belonging to the authenticated user's workspace. Supports
    ``?search=`` across ``first_name``, ``last_name``,
    ``phone_number``, and ``email``.

    **POST** ``/customers/`` — Create a new customer. The ``workspace``
    is resolved from the authenticated user's active workspace
    membership; clients must not provide it in the request body.
    """

    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = [
        "first_name",
        "last_name",
        "phone_number",
        "email",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Return only customers scoped to the user's workspace."""
        workspace = get_active_workspace(self.request)
        return Customer.objects.filter(workspace=workspace)


class CustomerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a customer.

    **GET** ``/customers/<uuid>/`` — Returns the customer details.

    **PATCH** ``/customers/<uuid>/`` — Partial update of the customer.

    **DELETE** ``/customers/<uuid>/`` — Permanently removes the
    customer from the database.

    Returns **404** if the customer does not exist or belongs to a
    different workspace.
    """

    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Scope to customers in the user's workspace.

        Because ``get_object()`` calls ``filter_queryset()`` on this
        queryset, customers in other workspaces will naturally
        return **404**.
        """
        workspace = get_active_workspace(self.request)
        return Customer.objects.filter(workspace=workspace)
