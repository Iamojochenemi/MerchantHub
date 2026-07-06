"""
Reusable HTTP client for the Nomba API.

Wraps ``requests.Session`` with pre-configured base URL, timeouts,
and default headers. All Nomba API calls should go through this
client to ensure consistent behaviour.
"""

from __future__ import annotations

from typing import Any

import requests

from apps.payments.integrations.nomba.exceptions import (
    NombaAuthenticationError,
    NombaConnectionError,
    NombaInvalidResponseError,
    NombaRequestError,
)


class NombaClient:
    """Low-level HTTP client for the Nomba API.

    Parameters
    ----------
    base_url:
        The base URL of the Nomba API (e.g. ``"https://api.nomba.com"``).
    timeout:
        Tuple of ``(connect_timeout, read_timeout)`` in seconds.
        Defaults to ``(10, 30)``.
    """

    def __init__(
        self,
        base_url: str,
        timeout: tuple[float, float] = (10.0, 30.0),
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # Public HTTP methods
    # ------------------------------------------------------------------

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        """Send an HTTP GET request to the Nomba API.

        Parameters
        ----------
        path:
            The URL path relative to ``base_url`` (e.g. ``/transactions/123``).
        params:
            Optional query-string parameters.
        headers:
            Optional additional HTTP headers.

        Returns
        -------
        requests.Response
            The raw response object.

        Raises
        ------
        NombaConnectionError
            If a network error or timeout occurs.
        NombaAuthenticationError
            If Nomba returns ``401`` or ``403``.
        NombaRequestError
            If Nomba returns any other non-2xx status code.
        """
        return self._request("GET", path, params=params, headers=headers)

    def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        """Send an HTTP POST request to the Nomba API.

        Parameters
        ----------
        path:
            The URL path relative to ``base_url`` (e.g. ``/v1/auth/token/issue``).
        json:
            Optional JSON-serialisable request body.
        headers:
            Optional additional HTTP headers.

        Returns
        -------
        requests.Response
            The raw response object.

        Raises
        ------
        NombaConnectionError
            If a network error or timeout occurs.
        NombaAuthenticationError
            If Nomba returns ``401`` or ``403``.
        NombaRequestError
            If Nomba returns any other non-2xx status code.
        """
        return self._request("POST", path, json=json, headers=headers)

    def close(self) -> None:
        """Close the underlying HTTP session and release resources."""
        self._session.close()

    def __del__(self) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_json(response: requests.Response) -> dict[str, Any]:
        """Parse a response body as JSON, raising a custom exception on failure.

        Parameters
        ----------
        response:
            The ``requests.Response`` to parse.

        Returns
        -------
        dict[str, Any]
            The parsed JSON body.

        Raises
        ------
        NombaInvalidResponseError
            If the response body is not valid JSON.
        """
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise NombaInvalidResponseError(
                f"Nomba returned an invalid JSON response "
                f"(HTTP {response.status_code}): {response.text!r}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        """Execute an HTTP request and handle common error cases.

        Parameters
        ----------
        method:
            HTTP method (``"GET"`` or ``"POST"``).
        path:
            The URL path relative to ``base_url``.
        params:
            Optional query-string parameters.
        json:
            Optional JSON-serialisable request body (POST only).
        headers:
            Optional additional HTTP headers.

        Returns
        -------
        requests.Response
            The raw response object.

        Raises
        ------
        NombaConnectionError
            For network errors and timeouts.
        NombaAuthenticationError
            For ``401`` / ``403`` responses.
        NombaRequestError
            For other non-2xx responses.
        """
        url = f"{self.base_url}{path}"

        try:
            response = self._session.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise NombaConnectionError(
                f"Request to Nomba timed out after {self.timeout}: {exc}"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise NombaConnectionError(
                f"Could not connect to Nomba at {url}: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise NombaAuthenticationError(
                f"Nomba authentication failed (HTTP {response.status_code}): "
                f"{response.text}"
            )

        if not response.ok:
            raise NombaRequestError(
                f"Nomba returned HTTP {response.status_code} for {method} {path}",
                status_code=response.status_code,
                response_body=response.text,
            )

        return response
