"""
Comprehensive unit tests for ``NombaCheckoutService`` and ``CheckoutOrderResult``.

All HTTP-level interactions are mocked — no real network calls are made.
The mock response bodies are designed to match Nomba's documented
checkout API schema.

Test coverage
-------------
- Successful order creation with auto-generated order reference
- Successful order creation with custom order reference
- All optional fields are included when provided
- Optional fields are excluded when not provided
- NombaCheckoutService falls back to ``settings.NOMBA_BASE_URL`` when
  ``base_url`` is not passed explicitly
- Authentication failure via HTTP 401/403 (``NombaClient`` layer)
- Network timeout
- DNS / connection failure
- Malformed JSON response body
- Missing ``data`` envelope in response
- Missing ``checkoutLink`` in data
- Response body that is not a JSON object
- Unexpected HTTP 500
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

import requests

from apps.payments.integrations.nomba.checkout import (
    CheckoutOrderResult,
    NombaCheckoutService,
)
from apps.payments.integrations.nomba.exceptions import (
    NombaAuthenticationError,
    NombaConnectionError,
    NombaInvalidResponseError,
    NombaRequestError,
)

# Minimal settings for services that read NOMBA_BASE_URL at runtime.
NOMBA_SETTINGS = {
    "NOMBA_BASE_URL": "https://sandbox.nomba.com",
}

# A realistic Nomba checkout success response (matching sandbox format).
_REAL_CHECKOUT_RESPONSE = {
    "code": "00",
    "description": "checkout order created successful",
    "status": False,
    "data": {
        "success": True,
        "message": "success",
        "orderReference": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "checkoutLink": (
            "https://pay.nomba.com/sandbox/"
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        ),
    },
}

_CHECKOUT_LINK = _REAL_CHECKOUT_RESPONSE["data"]["checkoutLink"]
_ORDER_REF = _REAL_CHECKOUT_RESPONSE["data"]["orderReference"]


# ======================================================================
# NombaCheckoutService — create_order scenarios
# ======================================================================


@override_settings(**NOMBA_SETTINGS)
class NombaCheckoutServiceTests(SimpleTestCase):
    """Test every path through ``create_order()``."""

    def setUp(self) -> None:
        """Create a service instance with a dummy token for all tests."""
        self.service = NombaCheckoutService(
            access_token="test-access-token",
            account_id="test-account-id",
        )

    # ------------------------------------------------------------------
    # Successful order creation — auto-generated reference
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_successful_order_with_auto_reference(
        self, mock_client: object
    ) -> None:
        """A valid response with auto-generated reference returns
        ``CheckoutOrderResult``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = _REAL_CHECKOUT_RESPONSE

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        result: CheckoutOrderResult = self.service.create_order(
            amount="10000.00",
        )

        self.assertIsInstance(result, CheckoutOrderResult)
        self.assertEqual(result.checkout_link, _CHECKOUT_LINK)
        self.assertEqual(result.order_reference, _ORDER_REF)
        self.assertEqual(result.raw_response, _REAL_CHECKOUT_RESPONSE)

        # Verify the payload sent to the client.
        call_kwargs = mock_client.post.call_args.kwargs
        sent_payload = call_kwargs["json"]
        self.assertEqual(sent_payload["order"]["amount"], "10000.00")
        self.assertEqual(sent_payload["order"]["currency"], "NGN")
        # orderReference should be auto-generated (a UUID).
        self.assertIn(
            "orderReference", sent_payload["order"],
        )
        self.assertIsNotNone(sent_payload["order"]["orderReference"])
        self.assertFalse(sent_payload["tokenizeCard"])

        # Verify headers.
        sent_headers = call_kwargs["headers"]
        self.assertEqual(
            sent_headers["Authorization"], "Bearer test-access-token",
        )
        self.assertEqual(sent_headers["accountId"], "test-account-id")

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_auto_reference_is_uuid_format(
        self, mock_client: object
    ) -> None:
        """When order_reference is omitted, a UUID v4 is generated."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = _REAL_CHECKOUT_RESPONSE

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        self.service.create_order(amount="5000.00")

        sent_ref = mock_client.post.call_args.kwargs["json"]["order"][
            "orderReference"
        ]
        # UUID v4 pattern: 8-4-4-4-12 hex digits with version 4.
        self.assertRegex(
            sent_ref,
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        )

    # ------------------------------------------------------------------
    # Successful order creation — custom reference
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_successful_order_with_custom_reference(
        self, mock_client: object
    ) -> None:
        """A custom ``order_reference`` is passed through to the API."""
        from unittest.mock import Mock

        custom_ref = "my-custom-ref-001"

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "code": "00",
            "description": "checkout order created successful",
            "status": False,
            "data": {
                "success": True,
                "message": "success",
                "orderReference": custom_ref,
                "checkoutLink": (
                    f"https://pay.nomba.com/sandbox/{custom_ref}"
                ),
            },
        }

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        result = self.service.create_order(
            amount="2500.00",
            order_reference=custom_ref,
        )

        self.assertEqual(result.order_reference, custom_ref)
        self.assertEqual(
            result.checkout_link,
            f"https://pay.nomba.com/sandbox/{custom_ref}",
        )
        # Verify the same reference was sent in the payload.
        sent_ref = mock_client.post.call_args.kwargs["json"]["order"][
            "orderReference"
        ]
        self.assertEqual(sent_ref, custom_ref)

    # ------------------------------------------------------------------
    # Optional fields
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_optional_fields_are_included_when_provided(
        self, mock_client: object
    ) -> None:
        """``callback_url``, ``customer_email``, and ``metadata`` are
        included in the payload when provided."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = _REAL_CHECKOUT_RESPONSE

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        self.service.create_order(
            amount="10000.00",
            callback_url="https://merchant.com/callback",
            customer_email="customer@example.com",
            metadata={"source": "web", "campaign": "summer"},
        )

        sent = mock_client.post.call_args.kwargs["json"]
        order = sent["order"]

        self.assertEqual(
            order["callbackUrl"], "https://merchant.com/callback",
        )
        self.assertEqual(
            order["customerEmail"], "customer@example.com",
        )
        self.assertEqual(
            sent["meta"], {"source": "web", "campaign": "summer"},
        )

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_optional_fields_are_excluded_when_not_provided(
        self, mock_client: object
    ) -> None:
        """``callback_url``, ``customer_email``, and ``metadata`` are
        omitted from the payload when not provided."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = _REAL_CHECKOUT_RESPONSE

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        self.service.create_order(amount="10000.00")

        sent = mock_client.post.call_args.kwargs["json"]
        order = sent["order"]

        self.assertNotIn("callbackUrl", order)
        self.assertNotIn("customerEmail", order)
        self.assertNotIn("meta", sent)

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    def test_missing_access_token_raises_value_error(self) -> None:
        """Empty ``access_token`` raises ``ValueError`` on init."""
        with self.assertRaises(ValueError) as cm:
            NombaCheckoutService(
                access_token="",
                account_id="test-account-id",
            )
        self.assertIn("access_token", str(cm.exception))

    def test_missing_account_id_raises_value_error(self) -> None:
        """Empty ``account_id`` raises ``ValueError`` on init."""
        with self.assertRaises(ValueError) as cm:
            NombaCheckoutService(
                access_token="test-access-token",
                account_id="",
            )
        self.assertIn("account_id", str(cm.exception))

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_empty_amount_raises_value_error(
        self, mock_client: object
    ) -> None:
        """Empty ``amount`` raises ``ValueError``."""
        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(ValueError) as cm:
            self.service.create_order(amount="")
        self.assertIn("amount", str(cm.exception))

    # ------------------------------------------------------------------
    # Base URL fallback
    # ------------------------------------------------------------------

    def test_base_url_fallback_to_settings(self) -> None:
        """When ``base_url`` is not passed, the service reads
        ``settings.NOMBA_BASE_URL``."""
        service = NombaCheckoutService(
            access_token="tok",
            account_id="aid",
        )
        self.assertEqual(service._base_url, "https://sandbox.nomba.com")

    # ------------------------------------------------------------------
    # Authentication failure (401 / 403) — client layer
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_authentication_failure_via_http_status(
        self, mock_client: object
    ) -> None:
        """HTTP 401 raises ``NombaAuthenticationError``."""
        from unittest.mock import Mock

        mock_client.post.side_effect = NombaAuthenticationError(
            "Nomba authentication failed (HTTP 401): Invalid token"
        )

        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaAuthenticationError):
            self.service.create_order(amount="10000.00")

    # ------------------------------------------------------------------
    # Timeout
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_timeout_raises_connection_error(
        self, mock_client: object
    ) -> None:
        """A request timeout raises ``NombaConnectionError``."""
        from unittest.mock import Mock

        mock_client.post.side_effect = NombaConnectionError(
            "Request to Nomba timed out"
        )

        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaConnectionError):
            self.service.create_order(amount="10000.00")

    # ------------------------------------------------------------------
    # Connection failure
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_connection_failure_raises_connection_error(
        self, mock_client: object
    ) -> None:
        """A DNS / network failure raises ``NombaConnectionError``."""
        from unittest.mock import Mock

        mock_client.post.side_effect = NombaConnectionError(
            "Could not connect to Nomba"
        )

        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaConnectionError):
            self.service.create_order(amount="10000.00")

    # ------------------------------------------------------------------
    # Malformed JSON
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_malformed_json_raises_invalid_response_error(
        self, mock_client: object
    ) -> None:
        """A non-JSON response body raises ``NombaInvalidResponseError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.text = "<html>Server Error</html>"
        mock_response.json.side_effect = requests.exceptions.JSONDecodeError(
            "Expecting value", "<html>", 0
        )

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaInvalidResponseError):
            self.service.create_order(amount="10000.00")

    # ------------------------------------------------------------------
    # Bad code
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_bad_code_raises_invalid_response_error(
        self, mock_client: object
    ) -> None:
        """A response with ``code != "00"`` raises
        ``NombaInvalidResponseError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "code": "99",
            "description": "Not found",
        }

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaInvalidResponseError) as cm:
            self.service.create_order(amount="10000.00")

        self.assertIn("99", str(cm.exception))

    # ------------------------------------------------------------------
    # Missing data envelope
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_missing_data_envelope_raises_invalid_response_error(
        self, mock_client: object
    ) -> None:
        """A 2xx response without a ``data`` field raises
        ``NombaInvalidResponseError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "code": "00",
        }

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaInvalidResponseError) as cm:
            self.service.create_order(amount="10000.00")

        self.assertIn("data", str(cm.exception))

    # ------------------------------------------------------------------
    # Missing success in data
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_data_success_false_raises_invalid_response_error(
        self, mock_client: object
    ) -> None:
        """A response with ``data.success=False`` raises
        ``NombaInvalidResponseError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "code": "00",
            "data": {
                "success": False,
                "message": "insufficient balance",
                "orderReference": "abc",
            },
        }

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaInvalidResponseError) as cm:
            self.service.create_order(amount="10000.00")

        self.assertIn("false", str(cm.exception).lower())

    # ------------------------------------------------------------------
    # Missing checkoutLink in data
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_missing_checkout_link_raises_invalid_response_error(
        self, mock_client: object
    ) -> None:
        """A response with ``data`` but no ``checkoutLink`` raises
        ``NombaInvalidResponseError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "code": "00",
            "data": {
                "success": True,
                "message": "success",
                "orderReference": "abc",
            },
        }

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaInvalidResponseError) as cm:
            self.service.create_order(amount="10000.00")

        self.assertIn("checkoutLink", str(cm.exception))

    # ------------------------------------------------------------------
    # Body is not a JSON object
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_body_is_not_a_dict_raises_invalid_response_error(
        self, mock_client: object
    ) -> None:
        """A JSON array response raises ``NombaInvalidResponseError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = ["not", "a", "dict"]

        mock_client.post.return_value = mock_response

        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaInvalidResponseError) as cm:
            self.service.create_order(amount="10000.00")

        self.assertIn("not a json object", str(cm.exception).lower())

    # ------------------------------------------------------------------
    # Unexpected HTTP error (500)
    # ------------------------------------------------------------------

    @patch.object(NombaCheckoutService, "_client", create=True)
    def test_unexpected_http_error_raises_request_error(
        self, mock_client: object
    ) -> None:
        """HTTP 500 raises ``NombaRequestError``."""
        from unittest.mock import Mock

        mock_client.post.side_effect = NombaRequestError(
            "Nomba returned HTTP 500 for POST /v1/checkout/order",
            status_code=500,
            response_body="Internal Server Error",
        )

        self.service._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaRequestError):
            self.service.create_order(amount="10000.00")
