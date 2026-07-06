"""
Transaction verification service for the Nomba API.

Provides :class:`NombaTransactionService` which checks the status of a
checkout transaction by calling Nomba's verification endpoint, and
:class:`TransactionVerificationResult` which encapsulates the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.payments.integrations.nomba.auth import NombaAuthService
from apps.payments.integrations.nomba.client import NombaClient
from apps.payments.integrations.nomba.exceptions import (
    NombaAuthenticationError,
    NombaConnectionError,
    NombaInvalidResponseError,
    NombaRequestError,
)


@dataclass(frozen=True)
class TransactionVerificationResult:
    """The result of verifying a Nomba transaction.

    Parameters
    ----------
    is_successful:
        Whether Nomba reports the transaction as successful
        (``data.status == "SUCCESS"``).
    nomba_status:
        The raw status string from Nomba (e.g. ``"SUCCESS"``,
        ``"PENDING"``, ``"FAILED"``).
    order_reference:
        The Nomba order reference that was checked.
    raw_response:
        The complete Nomba API response body, preserved for debugging
        and auditing purposes.
    """

    is_successful: bool
    nomba_status: str
    order_reference: str
    raw_response: dict[str, Any]


class NombaTransactionService:
    """Verify the status of Nomba checkout transactions.

    Calls Nomba's ``GET /v1/transactions/accounts/single`` endpoint
    with the ``orderReference`` to determine the current payment
    status.

    This service is **auth-agnostic** — it expects a valid bearer
    token and account identifier to be supplied by the caller.

    Usage::

        txn = NombaTransactionService(
            access_token=token.access_token,
            account_id=settings.NOMBA_ACCOUNT_ID,
        )
        result = txn.verify_transaction(order_reference="...")
        print(f"Paid: {result.is_successful}")
    """

    # Default timeout: 10 s connect, 30 s read.
    _REQUEST_TIMEOUT: tuple[float, float] = (10.0, 30.0)

    def __init__(
        self,
        access_token: str,
        account_id: str,
        base_url: str = "",
    ) -> None:
        """Initialise the transaction service.

        Parameters
        ----------
        access_token:
            A valid Nomba OAuth2 bearer token.
        account_id:
            The Nomba account identifier for the ``accountId`` header.
        base_url:
            The Nomba API base URL. Falls back to ``NOMBA_BASE_URL``
            setting if empty.
        """
        self._access_token = access_token
        self._account_id = account_id
        self._base_url = base_url or settings.NOMBA_BASE_URL

        if not self._access_token:
            raise ValueError(
                "access_token is required and must be non-empty."
            )
        if not self._account_id:
            raise ValueError(
                "account_id is required and must be non-empty."
            )

        self._client = NombaClient(
            base_url=self._base_url,
            timeout=self._REQUEST_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_transaction(
        self,
        order_reference: str,
    ) -> TransactionVerificationResult:
        """Verify the status of a Nomba checkout transaction.

        Sends a ``GET`` request to
        ``/v1/transactions/accounts/single?orderReference=<ref>``.

        Parameters
        ----------
        order_reference:
            The Nomba order reference (stored as
            ``payment.provider_reference``) to verify.

        Returns
        -------
        TransactionVerificationResult
            A frozen dataclass with the verification outcome.

        Raises
        ------
        NombaAuthenticationError
            If the access token is invalid or expired (HTTP 401/403).
        NombaConnectionError
            If a network error or timeout occurs.
        NombaInvalidResponseError
            If Nomba returns a malformed response.
        NombaRequestError
            If Nomba returns an unexpected non-2xx response.
        """
        if not order_reference:
            raise ValueError(
                "order_reference is required and must be non-empty."
            )

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "accountId": self._account_id,
        }

        response = self._client.get(
            "/v1/transactions/accounts/single",
            params={"orderReference": order_reference},
            headers=headers,
        )

        body: dict[str, Any] = NombaClient.parse_json(response)
        data: dict[str, Any] = self._validate_response(body)

        nomba_status: str = data.get("status", "")

        return TransactionVerificationResult(
            is_successful=nomba_status == "SUCCESS",
            nomba_status=nomba_status,
            order_reference=order_reference,
            raw_response=body,
        )

    # ------------------------------------------------------------------
    # Class method — verify with auto-auth
    # ------------------------------------------------------------------

    @classmethod
    def verify_with_auto_auth(
        cls,
        order_reference: str,
    ) -> TransactionVerificationResult:
        """Verify a transaction, obtaining a fresh token automatically.

        Convenience method that creates a ``NombaAuthService`` to
        obtain a token, then verifies the transaction.

        Parameters
        ----------
        order_reference:
            The Nomba order reference to verify.

        Returns
        -------
        TransactionVerificationResult
            The verification result.

        Raises
        ------
        Same as :meth:`verify_transaction`.
        """
        auth = NombaAuthService()
        token = auth.get_access_token()

        svc = cls(
            access_token=token.access_token,
            account_id=settings.NOMBA_ACCOUNT_ID,
        )
        return svc.verify_transaction(order_reference=order_reference)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_response(body: Any) -> dict[str, Any]:
        """Validate the Nomba transaction verification response.

        Nomba's documented success response::

            {
                "code": "00",
                "data": {
                    "status": "SUCCESS",
                    ...
                }
            }

        Parameters
        ----------
        body:
            The parsed JSON response body.

        Returns
        -------
        dict[str, Any]
            The validated ``data`` sub-dict.

        Raises
        ------
        NombaInvalidResponseError
            If the response is missing required fields or the
            ``code`` is not ``"00"``.
        """
        if not isinstance(body, dict):
            raise NombaInvalidResponseError(
                f"Nomba verification response body is not a JSON "
                f"object: {body!r}"
            )

        # Nomba returns code="00" for a successful API call
        code: Any = body.get("code")
        if code != "00":
            raise NombaInvalidResponseError(
                f"Nomba verification returned code={code!r} "
                f"(expected '00')"
            )

        data: Any = body.get("data")

        if not isinstance(data, dict):
            raise NombaInvalidResponseError(
                "Nomba verification response is missing the 'data' "
                "envelope"
            )

        if "status" not in data:
            raise NombaInvalidResponseError(
                "Nomba verification response 'data' is missing the "
                "'status' field"
            )

        return data
