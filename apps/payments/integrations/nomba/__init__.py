"""
Nomba payment integration for MerchantHub.

This package provides the authentication and HTTP client layer
for communicating with the Nomba API. Additional capabilities
(checkout, webhooks, payment verification) will be added in
subsequent PRs.
"""

from apps.payments.integrations.nomba.auth import NombaAuthService
from apps.payments.integrations.nomba.client import NombaClient
from apps.payments.integrations.nomba.exceptions import (
    NombaAuthenticationError,
    NombaConnectionError,
    NombaError,
    NombaInvalidResponseError,
    NombaRequestError,
)

__all__ = [
    "NombaAuthService",
    "NombaClient",
    "NombaError",
    "NombaAuthenticationError",
    "NombaConnectionError",
    "NombaInvalidResponseError",
    "NombaRequestError",
]
