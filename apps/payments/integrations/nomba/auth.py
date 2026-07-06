"""
Authentication layer for the Nomba API.

Provides :class:`NombaAuthService` which obtains OAuth2 access tokens
using the ``client_credentials`` grant type, and :class:`NombaAuthResult`
which encapsulates a successful authentication response.

Configuration
-------------
All configuration is read from Django settings (which in turn read
from environment variables):

- ``NOMBA_BASE_URL`` – base URL of the Nomba API
- ``NOMBA_CLIENT_ID`` – OAuth2 client identifier
- ``NOMBA_CLIENT_SECRET`` – OAuth2 client secret
- ``NOMBA_ACCOUNT_ID`` – Nomba account identifier
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.payments.integrations.nomba.client import NombaClient
from apps.payments.integrations.nomba.exceptions import (
    NombaAuthenticationError,
    NombaInvalidResponseError,
)


@dataclass(frozen=True)
class NombaAuthResult:
    """A successful Nomba authentication response.

    This dataclass exposes only the fields that are useful to consumers
    (checkout, payment verification, webhooks), shielding them from the
    Nomba API's internal envelope structure.

    Parameters
    ----------
    access_token:
        The JWT access token used to authorise subsequent API calls.
    refresh_token:
        A token that can be exchanged for a new ``access_token`` when
        the current one expires.
    business_id:
        The Nomba business identifier scoped to this account.
    expires_at:
        ISO-8601 timestamp indicating when the ``access_token`` expires.
    raw_response:
        The complete Nomba API response body, preserved for debugging
        and auditing purposes.  **Do not** depend on its structure in
        production code.
    """

    access_token: str
    refresh_token: str
    business_id: str
    expires_at: str
    raw_response: dict[str, Any]


class NombaAuthService:
    """Obtain OAuth2 access tokens from Nomba using ``client_credentials``.

    This service does **not** cache tokens — each call to
    :meth:`get_access_token` issues a fresh request to Nomba's
    token endpoint.  Token caching will be added in a follow-up PR.

    Usage::

        auth = NombaAuthService()
        result = auth.get_access_token()
        print(result.access_token)
    """

    # Default timeout: 10 s connect, 30 s read.
    _REQUEST_TIMEOUT: tuple[float, float] = (10.0, 30.0)

    def __init__(self) -> None:
        self._base_url = settings.NOMBA_BASE_URL
        self._client_id = settings.NOMBA_CLIENT_ID
        self._client_secret = settings.NOMBA_CLIENT_SECRET
        self._account_id = settings.NOMBA_ACCOUNT_ID

        self._validate_config()

        self._client = NombaClient(
            base_url=self._base_url,
            timeout=self._REQUEST_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_access_token(self) -> NombaAuthResult:
        """Obtain a fresh OAuth2 access token from Nomba.

        Sends a ``POST`` request to ``/v1/auth/token/issue`` with the
        ``client_credentials`` grant type, the configured client
        credentials, and the ``accountId`` header required by Nomba.

        The response is validated against Nomba's documented schema:

        * The ``code`` field **must** be ``"00"`` (success).
        * The ``data`` envelope **must** be present and contain an
          ``access_token`` field.

        Returns
        -------
        NombaAuthResult
            A frozen dataclass with the token data.

        Raises
        ------
        NombaAuthenticationError
            If Nomba rejects the credentials (HTTP 401/403) **or**
            returns a ``code`` other than ``"00"`` in a 2xx response.
        NombaConnectionError
            If a network error or timeout occurs.
        NombaInvalidResponseError
            If Nomba returns a malformed (non-JSON) response or the
            response structure does not match the documented schema.
        NombaRequestError
            If Nomba returns an unexpected non-2xx response.
        """
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        headers = {
            "accountId": self._account_id,
        }

        response = self._client.post(
            "/v1/auth/token/issue",
            json=payload,
            headers=headers,
        )

        body: dict[str, Any] = NombaClient.parse_json(response)
        data: dict[str, Any] = self._validate_response(body)

        return NombaAuthResult(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            business_id=data.get("businessId", ""),
            expires_at=data.get("expiresAt", ""),
            raw_response=body,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_response(body: Any) -> dict[str, Any]:
        """Validate the Nomba auth response envelope and return the ``data`` dict.

        Nomba's documented success schema is::

            {
                "code": "00",
                "description": "Success",
                "data": {
                    "access_token": "...",
                    "refresh_token": "...",
                    "businessId": "...",
                    "expiresAt": "..."
                }
            }

        On success the ``code`` field is the string ``"00"``.  Any other
        ``code`` value indicates an application-level error (e.g. invalid
        credentials), even when the HTTP status is 200.

        Parameters
        ----------
        body:
            The parsed JSON response body.

        Returns
        -------
        dict[str, Any]
            The ``data`` sub-dict from the Nomba response.

        Raises
        ------
        NombaInvalidResponseError
            If the body is not a dict, or is missing the ``data`` field,
            or ``data`` is missing the ``access_token`` field.
        NombaAuthenticationError
            If the ``code`` field is not ``"00"``.
        """
        if not isinstance(body, dict):
            raise NombaInvalidResponseError(
                f"Nomba auth response body is not a JSON object: {body!r}"
            )

        code: Any = body.get("code")
        description: str = body.get("description", "No description provided")

        if code != "00":
            raise NombaAuthenticationError(
                f"Nomba authentication failed (code={code!r}, "
                f"description={description!r})"
            )

        data: Any = body.get("data")

        if not isinstance(data, dict):
            raise NombaInvalidResponseError(
                f"Nomba auth response is missing the 'data' envelope "
                f"(code={code!r}, description={description!r})"
            )

        if not data.get("access_token"):
            raise NombaInvalidResponseError(
                f"Nomba auth response 'data' envelope is missing the "
                f"'access_token' field (code={code!r}, "
                f"description={description!r}). "
                f"Present keys in data: {list(data.keys())}"
            )

        return data

    def _validate_config(self) -> None:
        """Verify that all required Nomba settings are configured.

        Raises
        ------
        ValueError
            If any required setting is empty.
        """
        required = {
            "NOMBA_BASE_URL": self._base_url,
            "NOMBA_CLIENT_ID": self._client_id,
            "NOMBA_CLIENT_SECRET": self._client_secret,
            "NOMBA_ACCOUNT_ID": self._account_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                "The following Nomba settings are required but not set: "
                f"{', '.join(missing)}. "
                "Ensure they are defined in your Django settings or "
                "environment variables."
            )
