"""
Tests for NombaPaymentService.verify_and_update_payment.

Covers the full orchestration: verify with Nomba → update Payment
status → update Sale payment_status.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.payments.integrations.nomba.services import (
    NombaPaymentService,
    PaymentVerificationResult,
)
from apps.payments.integrations.nomba.verification import (
    TransactionVerificationResult,
)

NOMBA_SETTINGS = {
    "NOMBA_BASE_URL": "https://sandbox.nomba.com",
    "NOMBA_CLIENT_ID": "test_client_id",
    "NOMBA_CLIENT_SECRET": "test_client_secret",
    "NOMBA_ACCOUNT_ID": "test_account_id",
}


def _make_mock_payment(
    provider_reference: str = "nomba-ref-001",
    status: str = "PENDING",
    payment_id: str | None = None,
):
    """Create a mock Payment object with the given attributes."""
    payment = MagicMock()
    payment.pk = payment_id or str(uuid.uuid4())
    payment.provider_reference = provider_reference
    payment.status = status
    payment.sale_id = str(uuid.uuid4())
    payment.amount = Decimal("5000.00")
    return payment


def _make_mock_sale(payment_status: str = "PENDING_PAYMENT"):
    """Create a mock Sale object."""
    sale = MagicMock()
    sale.pk = str(uuid.uuid4())
    sale.payment_status = payment_status
    return sale


# ======================================================================
# Service orchestration tests
# ======================================================================


@override_settings(**NOMBA_SETTINGS)
class NombaPaymentServiceOrchestrationTests(TestCase):
    """Verify the verify_and_update_payment orchestration."""

    def setUp(self) -> None:
        self.payment = _make_mock_payment(
            provider_reference="nomba-ref-001",
            status="PENDING",
        )
        self.sale = _make_mock_sale(payment_status="PENDING_PAYMENT")
        self.payment.sale = self.sale

    # ------------------------------------------------------------------
    # Successful payment flow
    # ------------------------------------------------------------------

    @patch("apps.payments.integrations.nomba.services.NombaAuthService")
    @patch("apps.payments.integrations.nomba.services.NombaTransactionService")
    @patch("apps.payments.integrations.nomba.services.PaymentService")
    def test_verify_success_updates_payment_and_sale(
        self,
        mock_payment_service,
        mock_transaction_service,
        mock_auth_service,
    ) -> None:
        """A SUCCESS verification updates Payment to SUCCESS and Sale to PAID."""
        # --- Mock auth ---
        mock_auth = MagicMock()
        mock_token = MagicMock()
        mock_token.access_token = "test-token"
        mock_auth.get_access_token.return_value = mock_token
        mock_auth_service.return_value = mock_auth

        # --- Mock transaction service ---
        mock_txn_svc = MagicMock()
        mock_txn_svc.verify_transaction.return_value = (
            TransactionVerificationResult(
                is_successful=True,
                nomba_status="SUCCESS",
                order_reference="nomba-ref-001",
                raw_response={},
            )
        )
        mock_transaction_service.return_value = mock_txn_svc

        # --- Mock PaymentService.update_payment_status ---
        updated_payment = MagicMock()
        updated_payment.pk = self.payment.pk
        updated_payment.status = "SUCCESS"
        updated_payment.sale_id = self.payment.sale_id
        updated_payment.sale = self.sale  # Must link back to the original sale
        mock_payment_service.update_payment_status.return_value = (
            updated_payment
        )

        # --- Execute ---
        result = NombaPaymentService.verify_and_update_payment(
            payment=self.payment,
        )

        # --- Assert ---
        self.assertIsInstance(result, PaymentVerificationResult)
        self.assertEqual(result.old_status, "PENDING")
        self.assertEqual(result.new_status, "SUCCESS")
        self.assertEqual(result.sale_payment_status, "PAID")
        self.assertEqual(result.nomba_status, "SUCCESS")

        # Verify the payment was updated to SUCCESS
        mock_payment_service.update_payment_status.assert_called_once()
        call_kwargs = mock_payment_service.update_payment_status.call_args.kwargs
        self.assertEqual(call_kwargs["new_status"], "SUCCESS")

        # Verify the sale was marked as PAID
        self.assertEqual(self.sale.payment_status, "PAID")
        self.sale.save.assert_called_once_with(
            update_fields=["payment_status", "updated_at"],
        )

    # ------------------------------------------------------------------
    # Failed payment flow
    # ------------------------------------------------------------------

    @patch("apps.payments.integrations.nomba.services.NombaAuthService")
    @patch("apps.payments.integrations.nomba.services.NombaTransactionService")
    @patch("apps.payments.integrations.nomba.services.PaymentService")
    def test_verify_failed_updates_payment_only(
        self,
        mock_payment_service,
        mock_transaction_service,
        mock_auth_service,
    ) -> None:
        """A FAILED verification updates Payment to FAILED but not Sale."""
        mock_auth = MagicMock()
        mock_token = MagicMock()
        mock_token.access_token = "test-token"
        mock_auth.get_access_token.return_value = mock_token
        mock_auth_service.return_value = mock_auth

        mock_txn_svc = MagicMock()
        mock_txn_svc.verify_transaction.return_value = (
            TransactionVerificationResult(
                is_successful=False,
                nomba_status="FAILED",
                order_reference="nomba-ref-001",
                raw_response={},
            )
        )
        mock_transaction_service.return_value = mock_txn_svc

        updated_payment = MagicMock()
        updated_payment.pk = self.payment.pk
        updated_payment.status = "FAILED"
        updated_payment.sale_id = self.payment.sale_id
        updated_payment.sale = self.sale
        mock_payment_service.update_payment_status.return_value = (
            updated_payment
        )

        result = NombaPaymentService.verify_and_update_payment(
            payment=self.payment,
        )

        self.assertEqual(result.old_status, "PENDING")
        self.assertEqual(result.new_status, "FAILED")
        self.assertEqual(result.nomba_status, "FAILED")

        # Sale should NOT be marked PAID
        self.assertEqual(self.sale.payment_status, "PENDING_PAYMENT")
        self.sale.save.assert_not_called()

    # ------------------------------------------------------------------
    # Pending payment (no status change)
    # ------------------------------------------------------------------

    @patch("apps.payments.integrations.nomba.services.NombaAuthService")
    @patch("apps.payments.integrations.nomba.services.NombaTransactionService")
    def test_verify_pending_does_not_update_status(
        self,
        mock_transaction_service,
        mock_auth_service,
    ) -> None:
        """A PENDING verification does not change Payment or Sale status."""
        mock_auth = MagicMock()
        mock_token = MagicMock()
        mock_token.access_token = "test-token"
        mock_auth.get_access_token.return_value = mock_token
        mock_auth_service.return_value = mock_auth

        mock_txn_svc = MagicMock()
        mock_txn_svc.verify_transaction.return_value = (
            TransactionVerificationResult(
                is_successful=False,
                nomba_status="PENDING",
                order_reference="nomba-ref-001",
                raw_response={},
            )
        )
        mock_transaction_service.return_value = mock_txn_svc

        result = NombaPaymentService.verify_and_update_payment(
            payment=self.payment,
        )

        self.assertEqual(result.old_status, "PENDING")
        self.assertEqual(result.new_status, "PENDING")
        self.assertEqual(result.nomba_status, "PENDING")

    # ------------------------------------------------------------------
    # Idempotency — skip if already SUCCESS
    # ------------------------------------------------------------------

    def test_verify_skips_when_already_success(self) -> None:
        """If the payment is already SUCCESS, verification is skipped."""
        payment = _make_mock_payment(
            provider_reference="nomba-ref-skip",
            status="SUCCESS",
        )
        payment.sale = _make_mock_sale(payment_status="PAID")

        result = NombaPaymentService.verify_and_update_payment(
            payment=payment,
        )

        # Should return immediately without calling Nomba
        self.assertEqual(result.new_status, "SUCCESS")
        self.assertEqual(result.nomba_status, "SUCCESS")
        self.assertEqual(result.sale_payment_status, "PAID")

    # ------------------------------------------------------------------
    # Missing provider_reference
    # ------------------------------------------------------------------

    def test_verify_without_provider_reference_raises_error(self) -> None:
        """A payment without provider_reference raises ValueError."""
        payment = _make_mock_payment(provider_reference="")

        with self.assertRaises(ValueError) as ctx:
            NombaPaymentService.verify_and_update_payment(
                payment=payment,
            )
        self.assertIn("provider_reference", str(ctx.exception))

    # ------------------------------------------------------------------
    # Access token from caller
    # ------------------------------------------------------------------

    @patch("apps.payments.integrations.nomba.services.NombaTransactionService")
    @patch("apps.payments.integrations.nomba.services.PaymentService")
    def test_verify_with_provided_token(
        self,
        mock_payment_service,
        mock_transaction_service,
    ) -> None:
        """A caller-provided access token is used instead of auto-auth."""
        mock_txn_svc = MagicMock()
        mock_txn_svc.verify_transaction.return_value = (
            TransactionVerificationResult(
                is_successful=True,
                nomba_status="SUCCESS",
                order_reference="nomba-ref-001",
                raw_response={},
            )
        )
        mock_transaction_service.return_value = mock_txn_svc

        updated_payment = MagicMock()
        updated_payment.pk = self.payment.pk
        updated_payment.status = "SUCCESS"
        updated_payment.sale_id = self.payment.sale_id
        updated_payment.sale = self.sale
        mock_payment_service.update_payment_status.return_value = (
            updated_payment
        )

        NombaPaymentService.verify_and_update_payment(
            payment=self.payment,
            access_token="explicit-token",
        )

        # Verify the transaction service was created with the explicit token
        call_kwargs = mock_transaction_service.call_args.kwargs
        self.assertEqual(call_kwargs["access_token"], "explicit-token")
