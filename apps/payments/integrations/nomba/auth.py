"""
Authentication layer for the Nomba API.

Provides :class:`NombaAuthService` which obtains OAuth2 access tokens
using the ``client_credentials`` grant type.

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

from typing import Any

from django.conf import settings

from apps.payments.integrations.nomba.client import NombaClient
from apps.payments.integrations.nomba.exceptions import (
    NombaAuthenticationError,
)


class NombaAuthService:
    """Obtain OAuth2 access tokens from Nomba using ``client_credentials``.

    This service does **not** cache tokens — each call to
    :meth:`get_access_token` issues a fresh request to Nomba's
    token endpoint. Token caching will be added in a follow-up PR.

    Usage::

        auth = NombaAuthService()
        token_data = auth.get_access_token()
        print(token_data["access_token"])
    """

    # Default timeout: 10 s connect, 30 s read.
    _REQUEST_TIMEOUT: tuple[float, float] = (10.0, 30.0)

    def __init__(self) -> None:
        self._base_url = settings.NOMBA_BASE_URL
        self._client_id = settings.NOMBA_CLIENT_ID
        self._client_secret = settings.NOMBA_CLIENT_SECRET
        # Stored for use by future capabilities (checkout, webhooks).
        self._account_id = settings.NOMBA_ACCOUNT_ID

        self._validate_config()

        self._client = NombaClient(
            base_url=self._base_url,
            timeout=self._REQUEST_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_access_token(self) -> dict[str, Any]:
        """Obtain a fresh OAuth2 access token from Nomba.

        Sends a ``POST`` request to ``/auth/token/issue`` with the
        ``client_credentials`` grant type, the configured client
        credentials, and the ``accountId`` header required by Nomba.

        Returns
        -------
        dict
            The parsed JSON response from Nomba. Typically contains
            ``access_token``, ``token_type``, ``expires_in``, and
            ``account_id`` keys.

        Raises
        ------
        NombaAuthenticationError
            If Nomba rejects the credentials.
        NombaConnectionError
            If a network error or timeout occurs.
        NombaInvalidResponseError
            If Nomba returns a malformed (non-JSON) response.
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
            "/auth/token/issue",
            json=payload,
            headers=headers,
        )

        body: dict[str, Any] = NombaClient.parse_json(response)

        # Nomba may return an error structure inside a 2xx response.
        if body.get("status") is False or body.get("error"):
            raise NombaAuthenticationError(
                f"Nomba returned an error in the token response: {body}"
            )

        return body

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
