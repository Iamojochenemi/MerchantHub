"""
Comprehensive unit tests for ``NombaAuthService``.

All HTTP-level interactions are mocked — no real network calls are
made.  Covers every error path defined in the authentication flow:

- Successful token retrieval
- Authentication failure (HTTP 401/403)
- Timeout
- Connection failure (DNS / network)
- Malformed (non-JSON) response body
- Unexpected HTTP error (500)
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

import requests

from apps.payments.integrations.nomba.auth import NombaAuthService
from apps.payments.integrations.nomba.exceptions import (
    NombaAuthenticationError,
    NombaConnectionError,
    NombaInvalidResponseError,
    NombaRequestError,
)

# Minimal settings required for NombaAuthService to initialise.
NOMBA_SETTINGS = {
    "NOMBA_BASE_URL": "https://api.nomba.com",
    "NOMBA_CLIENT_ID": "test-client-id",
    "NOMBA_CLIENT_SECRET": "test-client-secret",
    "NOMBA_ACCOUNT_ID": "test-account-id",
}


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
    # Make ``.ok`` return the correct value.
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
        self.assertEqual(auth._base_url, "https://api.nomba.com")
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
        """A valid token response returns the parsed JSON body."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "access_token": "eyJhbGci...",
            "token_type": "Bearer",
            "expires_in": 3600,
            "account_id": "test-account-id",
        }

        mock_client.post.return_value = mock_response
        mock_client.parse_json = lambda r: r.json()

        auth = NombaAuthService()
        # Replace the real client with our mock.
        auth._client = mock_client  # type: ignore[assignment]

        result = auth.get_access_token()

        self.assertEqual(result["access_token"], "eyJhbGci...")
        self.assertEqual(result["token_type"], "Bearer")
        self.assertEqual(result["expires_in"], 3600)
        mock_client.post.assert_called_once()

    # ------------------------------------------------------------------
    # Authentication failure (401 / 403)
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

    @patch.object(NombaAuthService, "_client", create=True)
    def test_authentication_failure_via_error_body(
        self, mock_client: object
    ) -> None:
        """A 2xx response with an error body raises ``NombaAuthenticationError``."""
        from unittest.mock import Mock

        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "status": False,
            "error": "invalid_client",
            "message": "Invalid client credentials",
        }

        mock_client.post.return_value = mock_response
        mock_client.parse_json = lambda r: r.json()

        auth = NombaAuthService()
        auth._client = mock_client  # type: ignore[assignment]

        with self.assertRaises(NombaAuthenticationError):
            auth.get_access_token()

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
            "Nomba returned HTTP 500 for POST /auth/token/issue",
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
        from apps.payments.integrations.nomba.client import NombaClient

        resp = _fake_response(200, {"key": "value"})
        result = NombaClient.parse_json(resp)
        self.assertEqual(result, {"key": "value"})

    def test_malformed_json_raises_invalid_response_error(self) -> None:
        """``parse_json`` raises ``NombaInvalidResponseError`` for bad JSON."""
        from apps.payments.integrations.nomba.client import NombaClient

        resp = _fake_response(200, text="not-json")
        with self.assertRaises(NombaInvalidResponseError):
            NombaClient.parse_json(resp)
