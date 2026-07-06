"""
Comprehensive unit tests for ``NombaAuthService`` and ``NombaAuthResult``.

All HTTP-level interactions are mocked — no real network calls are
made.  The mock response bodies are designed to match the **real**
Nomba sandbox API response schema (discovered empirically and
confirmed by the official documentation).

Test coverage
-------------
- Configuration validation (missing settings)
- Successful authentication (realistic Nomba response including the
  unreliable ``"status": false`` field that must **not** block success)
- Authentication failure via HTTP 401/403 (``NombaClient`` layer)
- Authentication failure via Nomba error ``code`` (e.g. ``"96"``)
- Network timeout
- DNS / connection failure
- Malformed JSON response body
- Missing ``data`` envelope in response
- Missing ``access_token`` inside ``data``
- Response body that is not a JSON object
- Unexpected HTTP 500
- ``NombaClient.parse_json`` (valid JSON / malformed JSON)
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

import requests

from apps.payments.integrations.nomba.auth import (
    NombaAuthResult,
    NombaAuthService,
)
from apps.payments.integrations.nomba.client import NombaClient
from apps.payments.integrations.nomba.exceptions import (
    NombaAuthenticationError,
    NombaConnectionError,
    NombaInvalidResponseError,
    NombaRequestError,
)

# Minimal settings required for NombaAuthService to initialise.
NOMBA_SETTINGS = {
    "NOMBA_BASE_URL": "https://sandbox.nomba.com",
    "NOMBA_CLIENT_ID": "test-client-id",
    "NOMBA_CLIENT_SECRET": "test-client-secret",
    "NOMBA_ACCOUNT_ID": "test-account-id",
}

# A realistic Nomba success response body (observed from the real
# sandbox environment).  Note that ``"status": false`` appears even
# on a successful authentication — it is not a reliable indicator.
_REAL_SUCCESS_BODY = {
    "code": "00",
    "description": "Successful",
    "status": False,
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dummy",
        "refresh_token": "01h4gdx2tctxfjgacbdwrcvs5d1688473602892",
        "businessId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "expiresAt": "2026-07-07T12:00:00Z",
    },
}

_SUCCESS_TOKEN = _REAL_SUCCESS_BODY["data"]["access_token"]
_SUCCESS_REFRESH = _REAL_SUCCESS_BODY["data"]["refresh_token"]
_SUCCESS_BUSINESS_ID = _REAL_SUCCESS_BODY["data"]["businessId"]
_SUCCESS_EXPIRES_AT = _REAL_SUCCESS_BODY["data"]["expiresAt"]


def _fake_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
) -> requests.Response:
    """Build a lightweight ``requests.Response`` stub.

    Parameters
    ----------
    status_code:
        The HTTP status code.
    json_data:
        Data that ``.json()`` returns.  Will be serialised with
        ``json.dumps`` so that ``.json()`` works correctly.
    text:
        The raw body text (used when ``json_data`` is ``None``).
    """
    import json

    resp = requests.Response()
    resp.status_code = status_code
    if json_data is not None:
        resp._content = json.dumps(json_data).encode("utf-8")
    else:
        resp._content = text.encode("utf-8")
    resp.raw = None  # type: ignore[attr-defined]
    return resp


# ======================================================================
# NombaAuthService — configuration validation
# ======================================================================


class NombaAuthServiceConfigTests(SimpleTestCase):
    """Verify that missing settings raise ``ValueError`` on init."""

    @override_settings(
        NOMBA_BASE_URL="",
        NOMBA_CLIENT_ID="test-client-id",
        NOMBA_CLIENT_SECRET="test-client-secret",
        NOMBA_ACCOUNT_ID="test-account-id",
    )
    def test_missing_base_url_raises_value_error(self) -> None:
        """Init fails when ``NOMBA_BASE_URL`` is empty."""
        with self.assertRaises(ValueError):
            NombaAuthService()

    @override_settings(
        NOMBA_BASE_URL="https://api.nomba.com",
        NOMBA_CLIENT_ID="",
        NOMBA_CLIENT_SECRET="test-client-secret",
        NOMBA_ACCOUNT_ID="test-account-id",
    )
    def test_missing_client_id_raises_value_error(self) -> None:
        """Init fails when ``NOMBA_CLIENT_ID`` is empty."""
        with self.assertRaises(ValueError):
            NombaAuthService()

    @override_settings(**NOMBA_SETTINGS)
    def test_valid_config_succeeds(self) -> None:
        """Init succeeds when all settings are populated."""
        auth = NombaAuthService()
        self.assertEqual(auth._base_url, "https://sandbox.nomba.com")
        self.assertEqual(auth._client_id, "test-client-id")
        self.assertEqual(auth._client_secret, "test-client-secret")
        self.assertEqual(auth._account_id, "test-account-id")


# ======================================================================
# NombaAuthService — get_access_token scenarios
# ======================================================================


@override_settings(**NOMBA_SETTINGS)
class NombaAuthServiceTokenTests(SimpleTestCase):
    """Test every path through ``get_access_token()``."""

    # ------------------------------------------------------------------
    # Successful authentication
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
    def test_successful_authentication(self, mock_client: object) -> None:
        """A valid Nomba response returns ``NombaAuthResult`` with the
        expected fields, even when ``"status": false`` is present."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = _REAL_SUCCESS_BODY

        mock_client.post.return_value = mock_response

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        result: NombaAuthResult = auth.get_access_token()

        self.assertIsInstance(result, NombaAuthResult)
        self.assertEqual(result.access_token, _SUCCESS_TOKEN)
        self.assertEqual(result.refresh_token, _SUCCESS_REFRESH)
        self.assertEqual(result.business_id, _SUCCESS_BUSINESS_ID)
        self.assertEqual(result.expires_at, _SUCCESS_EXPIRES_AT)
        # raw_response must contain the full envelope for debugging.
        self.assertEqual(result.raw_response, _REAL_SUCCESS_BODY)

        mock_client.post.assert_called_once()

    # ------------------------------------------------------------------
    # Authentication failure (401 / 403) — client layer
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
    def test_authentication_failure_via_http_status(
        self, mock_client: object
    ) -> None:
        """HTTP 401 raises ``NombaAuthenticationError``."""
        from unittest.mock import Mock

        mock_client.post.side_effect = NombaAuthenticationError(
            "Nomba authentication failed (HTTP 401): Invalid credentials"
        )

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaAuthenticationError):
            auth.get_access_token()

    # ------------------------------------------------------------------
    # Authentication failure via Nomba error code
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
    def test_authentication_failure_via_error_code(
        self, mock_client: object
    ) -> None:
        """A 2xx response with ``code != "00"`` raises
        ``NombaAuthenticationError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "code": "96",
            "description": "Invalid client credentials",
        }

        mock_client.post.return_value = mock_response

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaAuthenticationError) as cm:
            auth.get_access_token()

        self.assertIn("code='96'", str(cm.exception))
        self.assertIn("Invalid client credentials", str(cm.exception))

    # ------------------------------------------------------------------
    # Missing "code" field (defensive)
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
    def test_missing_code_field_raises_authentication_error(
        self, mock_client: object
    ) -> None:
        """A 2xx response without a ``code`` field raises
        ``NombaAuthenticationError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "description": "Something went wrong",
        }

        mock_client.post.return_value = mock_response

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaAuthenticationError) as cm:
            auth.get_access_token()

        self.assertIn("code=None", str(cm.exception))

    # ------------------------------------------------------------------
    # Missing "data" envelope
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
    def test_missing_data_envelope_raises_invalid_response_error(
        self, mock_client: object
    ) -> None:
        """A 2xx response with ``code="00"`` but no ``data`` raises
        ``NombaInvalidResponseError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "code": "00",
            "description": "Success",
        }

        mock_client.post.return_value = mock_response

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaInvalidResponseError) as cm:
            auth.get_access_token()

        self.assertIn("data", str(cm.exception))

    # ------------------------------------------------------------------
    # Missing "access_token" inside data
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
    def test_missing_access_token_raises_invalid_response_error(
        self, mock_client: object
    ) -> None:
        """A response with ``data`` but no ``access_token`` raises
        ``NombaInvalidResponseError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "code": "00",
            "description": "Success",
            "data": {
                "refresh_token": "abc",
                "businessId": "def",
                "expiresAt": "2026-07-07T12:00:00Z",
            },
        }

        mock_client.post.return_value = mock_response

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaInvalidResponseError) as cm:
            auth.get_access_token()

        self.assertIn("access_token", str(cm.exception))

    # ------------------------------------------------------------------
    # Body is not a JSON object (e.g. a JSON array)
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
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

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaInvalidResponseError) as cm:
            auth.get_access_token()

        self.assertIn("not a json object", str(cm.exception).lower())

    # ------------------------------------------------------------------
    # Timeout
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
    def test_timeout_raises_connection_error(
        self, mock_client: object
    ) -> None:
        """A request timeout raises ``NombaConnectionError``."""
        from unittest.mock import Mock

        mock_client.post.side_effect = NombaConnectionError(
            "Request to Nomba timed out"
        )

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaConnectionError):
            auth.get_access_token()

    # ------------------------------------------------------------------
    # Connection failure
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
    def test_connection_failure_raises_connection_error(
        self, mock_client: object
    ) -> None:
        """A DNS / network failure raises ``NombaConnectionError``."""
        from unittest.mock import Mock

        mock_client.post.side_effect = NombaConnectionError(
            "Could not connect to Nomba"
        )

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaConnectionError):
            auth.get_access_token()

    # ------------------------------------------------------------------
    # Malformed JSON
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
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

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaInvalidResponseError):
            auth.get_access_token()

    # ------------------------------------------------------------------
    # Unexpected HTTP error (500)
    # ------------------------------------------------------------------

    @patch.object(NombaAuthService, "_client", create=True)
    def test_unexpected_http_error_raises_request_error(
        self, mock_client: object
    ) -> None:
        """HTTP 500 raises ``NombaRequestError``."""
        from unittest.mock import Mock

        mock_client.post.side_effect = NombaRequestError(
            "Nomba returned HTTP 500 for POST /v1/auth/token/issue",
            status_code=500,
            response_body="Internal Server Error",
        )

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaRequestError):
            auth.get_access_token()


# ======================================================================
# NombaClient — parse_json
# ======================================================================


@override_settings(**NOMBA_SETTINGS)
class NombaClientParseJsonTests(SimpleTestCase):
    """Test the static ``parse_json`` helper directly."""

    def test_valid_json_returns_dict(self) -> None:
        """``parse_json`` returns the parsed dict for valid JSON."""
        resp = _fake_response(200, {"key": "value"})
        result = NombaClient.parse_json(resp)
        self.assertEqual(result, {"key": "value"})

    def test_malformed_json_raises_invalid_response_error(self) -> None:
        """``parse_json`` raises ``NombaInvalidResponseError`` for bad JSON."""
        resp = _fake_response(200, text="not-json")
        with self.assertRaises(NombaInvalidResponseError):
            NombaClient.parse_json(resp)
