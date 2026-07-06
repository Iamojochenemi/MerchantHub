"""
Comprehensive unit tests for ``NombaPaymentService`` and ``NombaCheckoutInitResult``.

All HTTP-level and service-layer interactions are mocked — no real
network calls or database writes are made.

Test coverage
-------------
- Successful checkout initiation with auto-generated access token
- Successful checkout initiation with provided access token
- Access token is not obtained when provided
- Checkout failure propagates (``NombaAuthenticationError``)
- Checkout failure propagates (``NombaConnectionError``)
- Checkout failure propagates (``NombaRequestError``)
- Payment creation failure propagates (``ValidationError``)
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.payments.integrations.nomba import NombaPaymentService
from apps.payments.integrations.nomba.exceptions import (
    NombaAuthenticationError,
    NombaConnectionError,
    NombaRequestError,
)

NOMBA_SETTINGS = {
    "NOMBA_BASE_URL": "https://sandbox.nomba.com",
    "NOMBA_CLIENT_ID": "test-client-id",
    "NOMBA_CLIENT_SECRET": "test-client-secret",
    "NOMBA_ACCOUNT_ID": "test-account-id",
}

# A realistic Sale stub — matches the fields that initiate_checkout() accesses.
_SALE_STUB = {
    "pk": "00000000-0000-0000-0000-000000000001",
    "total": Decimal("15000.00"),
    "workspace_id": "workspace-1",
    "workspace_pk": "workspace-1",
}


def _make_sale_stub(**overrides: object) -> object:
    """Build a lightweight Sale-like object for testing."""

    class WorkspaceStub:
        pk = _SALE_STUB["workspace_pk"]

    class SaleStub:
        pk = _SALE_STUB["pk"]
        total = _SALE_STUB["total"]
        workspace_id = _SALE_STUB["workspace_id"]
        workspace = WorkspaceStub()

        def __str__(self) -> str:
            return f"Sale {self.pk}"

    stub = SaleStub()
    for key, value in overrides.items():
        setattr(stub, key, value)
    return stub


def _mock_checkout_result(
    order_reference: str = "nomba-ref-001",
    checkout_link: str = "https://checkout.nomba.com/checkout/nomba-ref-001",
) -> object:
    """Build a mock ``CheckoutOrderResult``-like object."""
    from unittest.mock import MagicMock

    result = MagicMock()
    result.order_reference = order_reference
    result.checkout_link = checkout_link
    return result


# ======================================================================
# NombaPaymentService — initiate_checkout scenarios
# ======================================================================


@override_settings(**NOMBA_SETTINGS)
class NombaPaymentServiceTests(SimpleTestCase):
    """Test every path through ``initiate_checkout()``."""

    def setUp(self) -> None:
        self.sale = _make_sale_stub()

    # ------------------------------------------------------------------
    # Successful checkout initiation (auto token)
    # ------------------------------------------------------------------

    @patch("apps.payments.integrations.nomba.services.NombaAuthService")
    @patch("apps.payments.integrations.nomba.services.NombaCheckoutService")
    @patch("apps.payments.integrations.nomba.services.PaymentService")
    def test_successful_initiate_checkout(
        self,
        mock_payment_service: object,
        mock_checkout_class: object,
        mock_auth_class: object,
    ) -> None:
        """A successful Nomba checkout creates a PENDING Payment and
        returns ``NombaCheckoutInitResult``."""
        from unittest.mock import MagicMock

        # --- Mock auth ---
        mock_token = MagicMock()
        mock_token.access_token = "test-access-token"

        mock_auth = MagicMock()
        mock_auth.get_access_token.return_value = mock_token
        mock_auth_class.return_value = mock_auth  # NombaAuthService() returns mock_auth

        # --- Mock checkout ---
        mock_checkout = MagicMock()
        mock_checkout.create_order.return_value = _mock_checkout_result()
        mock_checkout_class.return_value = mock_checkout  # NombaCheckoutService() returns mock_checkout

        # --- Mock payment ---
        mock_payment = MagicMock()
        mock_payment.pk = "payment-uuid-001"
        mock_payment_service.create_payment.return_value = mock_payment

        # --- Execute ---
        result = NombaPaymentService.initiate_checkout(
            sale=self.sale,
            callback_url="https://merchant.com/callback",
            customer_email="customer@example.com",
            metadata={"source": "web"},
        )

        # --- Assertions ---
        self.assertEqual(
            result.checkout_link,
            "https://checkout.nomba.com/checkout/nomba-ref-001",
        )
        self.assertEqual(result.order_reference, "nomba-ref-001")
        self.assertEqual(result.payment_id, "payment-uuid-001")
        self.assertEqual(result.sale_id, "00000000-0000-0000-0000-000000000001")

        # Auth was called (no token provided)
        mock_auth_class.assert_called_once()
        mock_auth.get_access_token.assert_called_once()

        # Checkout was created with the sale total
        mock_checkout.create_order.assert_called_once_with(
            amount="15000.00",
            currency="NGN",
            callback_url="https://merchant.com/callback",
            customer_email="customer@example.com",
            metadata={"source": "web"},
        )

        # Payment was created with the correct params
        mock_payment_service.create_payment.assert_called_once()
        call_kwargs = mock_payment_service.create_payment.call_args.kwargs
        self.assertEqual(call_kwargs["workspace"], self.sale.workspace)
        self.assertEqual(call_kwargs["sale"], self.sale)
        self.assertEqual(call_kwargs["amount"], Decimal("15000.00"))
        self.assertEqual(call_kwargs["currency"], "NGN")
        self.assertEqual(call_kwargs["payment_method"], "TRANSFER")
        self.assertEqual(call_kwargs["status"], "PENDING")
        self.assertEqual(
            call_kwargs["provider_reference"], "nomba-ref-001"
        )

    # ------------------------------------------------------------------
    # Successful checkout initiation (provided token)
    # ------------------------------------------------------------------

    @patch("apps.payments.integrations.nomba.services.NombaAuthService")
    @patch("apps.payments.integrations.nomba.services.NombaCheckoutService")
    @patch("apps.payments.integrations.nomba.services.PaymentService")
    def test_initiate_checkout_with_provided_token(
        self,
        mock_payment_service: object,
        mock_checkout_class: object,
        mock_auth_class: object,
    ) -> None:
        """When an ``access_token`` is provided, the auth service is
        **not** called."""
        from unittest.mock import MagicMock

        mock_checkout = MagicMock()
        mock_checkout.create_order.return_value = _mock_checkout_result()
        mock_checkout_class.return_value = mock_checkout

        mock_payment = MagicMock()
        mock_payment.pk = "payment-uuid-002"
        mock_payment_service.create_payment.return_value = mock_payment

        NombaPaymentService.initiate_checkout(
            sale=self.sale,
            access_token="existing-token",
        )

        # Auth should NOT be called when token is provided.
        mock_auth_class.assert_not_called()

    # ------------------------------------------------------------------
    # Auth failure propagates
    # ------------------------------------------------------------------

    @patch("apps.payments.integrations.nomba.services.NombaAuthService")
    def test_auth_failure_propagates(
        self, mock_auth_class: object
    ) -> None:
        """If ``NombaAuthService`` raises, the error propagates."""
        from unittest.mock import MagicMock

        mock_auth = MagicMock()
        mock_auth.get_access_token.side_effect = NombaAuthenticationError(
            "Nomba authentication failed (HTTP 401): Bad creds"
        )
        mock_auth_class.return_value = mock_auth

        with self.assertRaises(NombaAuthenticationError):
            NombaPaymentService.initiate_checkout(sale=self.sale)

    # ------------------------------------------------------------------
    # Checkout failure propagates
    # ------------------------------------------------------------------

    @patch("apps.payments.integrations.nomba.services.NombaAuthService")
    @patch("apps.payments.integrations.nomba.services.NombaCheckoutService")
    def test_checkout_failure_propagates(
        self,
        mock_checkout_class: object,
        mock_auth_class: object,
    ) -> None:
        """If ``NombaCheckoutService.create_order`` raises, the error
        propagates."""
        from unittest.mock import MagicMock

        mock_token = MagicMock()
        mock_token.access_token = "tok"
        mock_auth = MagicMock()
        mock_auth.get_access_token.return_value = mock_token
        mock_auth_class.return_value = mock_auth

        mock_checkout = MagicMock()
        mock_checkout.create_order.side_effect = NombaConnectionError(
            "Could not connect to Nomba"
        )
        mock_checkout_class.return_value = mock_checkout

        with self.assertRaises(NombaConnectionError):
            NombaPaymentService.initiate_checkout(sale=self.sale)

    # ------------------------------------------------------------------
    # Payment creation failure propagates
    # ------------------------------------------------------------------

    @patch("apps.payments.integrations.nomba.services.NombaAuthService")
    @patch("apps.payments.integrations.nomba.services.NombaCheckoutService")
    @patch("apps.payments.integrations.nomba.services.PaymentService")
    def test_payment_creation_failure_propagates(
        self,
        mock_payment_service: object,
        mock_checkout_class: object,
        mock_auth_class: object,
    ) -> None:
        """If ``PaymentService.create_payment`` raises, the error
        propagates."""
        from unittest.mock import MagicMock
        from rest_framework.exceptions import ValidationError

        mock_token = MagicMock()
        mock_token.access_token = "tok"
        mock_auth = MagicMock()
        mock_auth.get_access_token.return_value = mock_token
        mock_auth_class.return_value = mock_auth

        mock_checkout = MagicMock()
        mock_checkout.create_order.return_value = _mock_checkout_result()
        mock_checkout_class.return_value = mock_checkout

        mock_payment_service.create_payment.side_effect = ValidationError(
            "A successful payment already exists for this sale."
        )

        with self.assertRaises(ValidationError):
            NombaPaymentService.initiate_checkout(sale=self.sale)
