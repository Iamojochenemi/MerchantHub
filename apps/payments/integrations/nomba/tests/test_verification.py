"""
Tests for NombaTransactionService.

Covers successful verification, failed/pending statuses, validation
errors (empty reference, bad response), and auto-auth convenience
method.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.payments.integrations.nomba.exceptions import (
    NombaAuthenticationError,
    NombaConnectionError,
    NombaInvalidResponseError,
    NombaRequestError,
)
from apps.payments.integrations.nomba.verification import (
    NombaTransactionService,
    TransactionVerificationResult,
)

# ------------------------------------------------------------------
# Sample responses
# ------------------------------------------------------------------

_REAL_SUCCESS_RESPONSE = {
    "code": "00",
    "data": {
        "status": "SUCCESS",
        "amount": "5000.00",
        "currency": "NGN",
        "customer": {"email": "test@example.com"},
        "transactionRef": "txn_001",
    },
}

_REAL_PENDING_RESPONSE = {
    "code": "00",
    "data": {
        "status": "PENDING",
        "amount": "5000.00",
    },
}

_REAL_FAILED_RESPONSE = {
    "code": "00",
    "data": {
        "status": "FAILED",
        "amount": "5000.00",
    },
}

_REAL_ERROR_RESPONSE = {
    "code": "99",
    "description": "Transaction not found",
}

NOMBA_SETTINGS = {
    "NOMBA_BASE_URL": "https://sandbox.nomba.com",
    "NOMBA_CLIENT_ID": "test_client_id",
    "NOMBA_CLIENT_SECRET": "test_client_secret",
    "NOMBA_ACCOUNT_ID": "test_account_id",
}


# ======================================================================
# Service tests
# ======================================================================


@override_settings(**NOMBA_SETTINGS)
class NombaTransactionServiceTests(TestCase):
    """Verify transaction verification with Nomba."""

    def setUp(self) -> None:
        """Create a service instance with a mock client."""
        self.service = NombaTransactionService(
            access_token="test-access-token",
            account_id="test-account-id",
            base_url="https://sandbox.nomba.com",
        )
        # Replace the real client with a mock for all tests
        self.service._client = MagicMock()

    def _mock_response(self, body: dict, status_code: int = 200) -> MagicMock:
        """Create a mock requests.Response with the given JSON body."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.ok = status_code < 400
        mock_resp.json.return_value = body
        mock_resp.text = json.dumps(body)
        return mock_resp

    # ------------------------------------------------------------------
    # Success
    # ------------------------------------------------------------------

    def test_verify_successful_transaction(self) -> None:
        """A SUCCESS transaction returns is_successful=True."""
        self.service._client.get.return_value = self._mock_response(
            _REAL_SUCCESS_RESPONSE,
        )
        result = self.service.verify_transaction(
            order_reference="test-ref-001",
        )
        self.assertIsInstance(result, TransactionVerificationResult)
        self.assertTrue(result.is_successful)
        self.assertEqual(result.nomba_status, "SUCCESS")
        self.assertEqual(result.order_reference, "test-ref-001")

    def test_verify_uses_correct_endpoint_and_params(self) -> None:
        """The GET request uses the correct path and query params."""
        self.service._client.get.return_value = self._mock_response(
            _REAL_SUCCESS_RESPONSE,
        )
        self.service.verify_transaction(order_reference="my-ref")

        self.service._client.get.assert_called_once()
        args, kwargs = self.service._client.get.call_args
        self.assertIn("/v1/transactions/accounts/single", args[0])
        self.assertEqual(
            kwargs["params"]["orderReference"], "my-ref",
        )
        self.assertIn("Authorization", kwargs["headers"])
        self.assertIn("accountId", kwargs["headers"])

    def test_verify_pending_transaction(self) -> None:
        """A PENDING transaction returns is_successful=False."""
        self.service._client.get.return_value = self._mock_response(
            _REAL_PENDING_RESPONSE,
        )
        result = self.service.verify_transaction(
            order_reference="test-ref-002",
        )
        self.assertFalse(result.is_successful)
        self.assertEqual(result.nomba_status, "PENDING")

    def test_verify_failed_transaction(self) -> None:
        """A FAILED transaction returns is_successful=False."""
        self.service._client.get.return_value = self._mock_response(
            _REAL_FAILED_RESPONSE,
        )
        result = self.service.verify_transaction(
            order_reference="test-ref-003",
        )
        self.assertFalse(result.is_successful)
        self.assertEqual(result.nomba_status, "FAILED")

    # ------------------------------------------------------------------
    # Validation errors
    # ------------------------------------------------------------------

    def test_empty_order_reference_raises_value_error(self) -> None:
        """An empty order_reference raises ValueError."""
        with self.assertRaises(ValueError):
            self.service.verify_transaction(order_reference="")

    def test_none_order_reference_raises_value_error(self) -> None:
        """A None order_reference raises ValueError."""
        with self.assertRaises(ValueError):
            self.service.verify_transaction(order_reference=None)  # type: ignore[arg-type]

    def test_empty_access_token_raises_value_error(self) -> None:
        """An empty access_token on init raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            NombaTransactionService(
                access_token="",
                account_id="test-account-id",
                base_url="https://sandbox.nomba.com",
            )
        self.assertIn("access_token", str(ctx.exception))

    def test_empty_account_id_raises_value_error(self) -> None:
        """An empty account_id on init raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            NombaTransactionService(
                access_token="test-token",
                account_id="",
                base_url="https://sandbox.nomba.com",
            )
        self.assertIn("account_id", str(ctx.exception))

    # ------------------------------------------------------------------
    # Response validation
    # ------------------------------------------------------------------

    def test_non_dict_body_raises_error(self) -> None:
        """A non-dict response body raises NombaInvalidResponseError."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.text = "[]"
        self.service._client.get.return_value = mock_resp

        with self.assertRaises(NombaInvalidResponseError):
            self.service.verify_transaction(order_reference="test-ref")

    def test_bad_code_raises_error(self) -> None:
        """A code other than '00' raises NombaInvalidResponseError."""
        self.service._client.get.return_value = self._mock_response(
            {"code": "99", "description": "Not found"},
        )
        with self.assertRaises(NombaInvalidResponseError) as ctx:
            self.service.verify_transaction(order_reference="test-ref")
        self.assertIn("99", str(ctx.exception))
        self.assertIn("expected '00'", str(ctx.exception))

    def test_missing_data_envelope_raises_error(self) -> None:
        """A response missing the 'data' envelope raises error."""
        self.service._client.get.return_value = self._mock_response(
            {"code": "00"},
        )
        with self.assertRaises(NombaInvalidResponseError):
            self.service.verify_transaction(order_reference="test-ref")

    def test_missing_status_field_raises_error(self) -> None:
        """A response missing the 'status' field raises error."""
        self.service._client.get.return_value = self._mock_response(
            {"code": "00", "data": {"amount": "5000"}},
        )
        with self.assertRaises(NombaInvalidResponseError):
            self.service.verify_transaction(order_reference="test-ref")

    # ------------------------------------------------------------------
    # Error propagation from client
    # ------------------------------------------------------------------

    def test_authentication_error_propagates(self) -> None:
        """HTTP 401 raises NombaAuthenticationError."""
        self.service._client.get.side_effect = NombaAuthenticationError(
            "Nomba authentication failed (HTTP 401)"
        )

        with self.assertRaises(NombaAuthenticationError):
            self.service.verify_transaction(order_reference="test-ref")

    def test_connection_error_propagates(self) -> None:
        """Network errors raise NombaConnectionError."""
        from requests.exceptions import ConnectionError as ReqConnectionError

        self.service._client.get.side_effect = NombaConnectionError("Connection failed")

        with self.assertRaises(NombaConnectionError):
            self.service.verify_transaction(order_reference="test-ref")

    def test_server_error_propagates(self) -> None:
        """HTTP 500 raises NombaRequestError."""
        self.service._client.get.side_effect = NombaRequestError(
            "Nomba returned HTTP 500",
            status_code=500,
            response_body="Server Error",
        )

        with self.assertRaises(NombaRequestError):
            self.service.verify_transaction(order_reference="test-ref")

    # ------------------------------------------------------------------
    # Auto-auth convenience method
    # ------------------------------------------------------------------

    @patch.object(NombaTransactionService, "verify_transaction")
    @patch("apps.payments.integrations.nomba.verification.NombaAuthService")
    def test_verify_with_auto_auth(
        self,
        mock_auth_service,
        mock_verify,
    ) -> None:
        """verify_with_auto_auth obtains a token and calls verify."""
        mock_auth = MagicMock()
        mock_token = MagicMock()
        mock_token.access_token = "auto-token"
        mock_auth.get_access_token.return_value = mock_token
        mock_auth_service.return_value = mock_auth

        mock_verify.return_value = TransactionVerificationResult(
            is_successful=True,
            nomba_status="SUCCESS",
            order_reference="auto-ref",
            raw_response={},
        )

        result = NombaTransactionService.verify_with_auto_auth(
            order_reference="auto-ref",
        )

        mock_auth_service.assert_called_once()
        mock_auth.get_access_token.assert_called_once()
        mock_verify.assert_called_once_with(order_reference="auto-ref")
        self.assertTrue(result.is_successful)
