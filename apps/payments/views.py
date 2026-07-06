"""
API views for the ``payments`` app.

Keeps views thin: validation is handled by ``PaymentSerializer``
and business logic is delegated to ``PaymentService``.
"""

from rest_framework import generics, permissions
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer
from apps.workspaces.utils import get_active_workspace


class PaymentListCreateView(generics.ListCreateAPIView):
    """List all payments in the workspace, or create a new one.

    **GET** ``/payments/`` — Returns a paginated list of payments
    belonging to the authenticated user's workspace. Supports
    ``?search=`` across ``provider_reference`` and
    ``external_reference``. Supports ordering by ``created_at``,
    ``amount``, and ``status``.

    **POST** ``/payments/`` — Record a new payment. The ``workspace``
    is resolved from the authenticated user's active workspace
    membership; clients must not provide it in the request body.
    """

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = [
        "provider_reference",
        "external_reference",
    ]
    ordering_fields = ["created_at", "amount", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Return only payments scoped to the user's workspace."""
        workspace = get_active_workspace(self.request)
        return Payment.objects.filter(workspace=workspace)


class PaymentDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a payment.

    **GET** ``/payments/<uuid>/`` — Returns the payment details.

    **PATCH** ``/payments/<uuid>/`` — Partial update of the payment
    (primarily used for status changes).

    **DELETE** is **not** allowed — payments are immutable records.

    Returns **404** if the payment does not exist or belongs to a
    different workspace.
    """

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        """Scope to payments in the user's workspace.

        Because ``get_object()`` calls ``filter_queryset()`` on this
        queryset, payments in other workspaces will naturally
        return **404**.
        """
        workspace = get_active_workspace(self.request)
        return Payment.objects.filter(workspace=workspace)
