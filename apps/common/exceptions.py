"""
Custom domain exceptions and DRF exception handler for MerchantHub.

Every API error returns a uniform JSON structure:

.. code:: json

    {
        "error": "Human-readable description.",
        "code": "MACHINE_READABLE_CODE",
        "details": {}
    }
"""

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class WorkspaceRequiredError(APIException):
    """Raised when a request is missing the ``X-Workspace-ID`` header."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "X-Workspace-ID header is required for this endpoint."
    default_code = "WORKSPACE_REQUIRED"


class NotWorkspaceMemberError(APIException):
    """Raised when the user is not a member of the requested workspace."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You are not a member of this workspace."
    default_code = "NOT_WORKSPACE_MEMBER"


class InsufficientStockError(APIException):
    """Raised when a sale cannot be completed due to insufficient stock."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Insufficient stock to complete the sale."
    default_code = "INSUFFICIENT_STOCK"

    def __init__(self, details: dict | None = None):
        if details is not None:
            self.detail = {
                "error": self.default_detail,
                "code": self.default_code,
                "details": details,
            }
        else:
            self.detail = {
                "error": self.default_detail,
                "code": self.default_code,
                "details": {},
            }


class PaymentExceedsTotalError(APIException):
    """Raised when a payment exceeds the remaining balance on a sale."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Payment amount exceeds the remaining sale balance."
    default_code = "PAYMENT_EXCEEDS_TOTAL"

    def __init__(self, details: dict | None = None):
        if details is not None:
            self.detail = {
                "error": self.default_detail,
                "code": self.default_code,
                "details": details,
            }
        else:
            self.detail = {
                "error": self.default_detail,
                "code": self.default_code,
                "details": {},
            }


class OwnerCannotRemoveSelfError(APIException):
    """Raised when the last owner tries to leave or demote themselves."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The last workspace owner cannot remove themselves."
    default_code = "OWNER_CANNOT_REMOVE_SELF"


class DuplicateSkuError(APIException):
    """Raised when a product SKU already exists in the workspace."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "DUPLICATE_SKU"

    def __init__(self, sku: str):
        self.detail = {
            "error": f"A product with SKU '{sku}' already exists in this workspace.",
            "code": self.default_code,
            "details": {"sku": sku},
        }


# ---------------------------------------------------------------------------
# Custom DRF exception handler
# ---------------------------------------------------------------------------


def custom_exception_handler(exc, context):
    """Convert all exceptions to ``{error, code, details}`` format.

    Handles DRF built-in exceptions and custom domain exceptions.
    Unhandled exceptions fall through to a generic 500 response.
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        # DRF ValidationError returns field-level errors under the key
        # matching the field name.  We preserve that structure while
        # adding a top-level error message.
        if hasattr(exc, "detail") and isinstance(exc.detail, dict):
            # Field-level validation errors
            response.data = {
                "error": "One or more fields are invalid.",
                "code": "VALIDATION_ERROR",
                "details": exc.detail,
            }
        elif hasattr(exc, "detail") and isinstance(exc.detail, list):
            # Non-field validation errors (e.g. ``["This field is required."]``)
            response.data = {
                "error": exc.detail[0] if exc.detail else "Validation error.",
                "code": getattr(exc, "default_code", "VALIDATION_ERROR"),
                "details": {},
            }
        elif not isinstance(response.data, dict):
            # Fallback for unexpected response shapes
            response.data = {
                "error": str(response.data),
                "code": getattr(exc, "default_code", "ERROR"),
                "details": {},
            }
        # Custom domain exceptions already have the correct dict shape
        # in their ``detail`` — do not re-wrap.

    return response
