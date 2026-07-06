"""
Custom exceptions for the Nomba integration.

Hierarchy::

    NombaError
    +-- NombaAuthenticationError
    +-- NombaConnectionError
    +-- NombaInvalidResponseError
    +-- NombaRequestError
"""

from __future__ import annotations


class NombaError(Exception):
    """Base exception for all Nomba integration errors."""


class NombaAuthenticationError(NombaError):
    """Raised when Nomba returns an authentication error
    (invalid/expired credentials, unauthorized client, etc.).
    """


class NombaConnectionError(NombaError):
    """Raised when a network-level error occurs (timeout, DNS failure,
    connection refused, etc.).
    """


class NombaInvalidResponseError(NombaError):
    """Raised when Nomba returns a response that cannot be parsed
    (e.g. malformed JSON, unexpected content type).
    """


class NombaRequestError(NombaError):
    """Raised when Nomba returns a non-2xx response that is not an
    authentication error.

    Attributes
    ----------
    status_code:
        The HTTP status code returned by Nomba.
    response_body:
        The raw response body, if available.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)
