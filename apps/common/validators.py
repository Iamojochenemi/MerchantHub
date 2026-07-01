"""
Shared validators for MerchantHub.

All validators raise ``django.core.exceptions.ValidationError``
so they can be used both as model-level validators and in DRF
serializer fields.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_positive_decimal(value) -> None:
    """Ensure *value* is strictly greater than zero.

    Accepts ``Decimal``, ``int``, and ``float`` types.
    """
    if value is None:
        return
    try:
        val = Decimal(str(value))
    except Exception as err:
        raise ValidationError(
            _("Value must be a numeric type."),
            code="invalid_numeric",
        ) from err
    if val <= Decimal("0"):
        raise ValidationError(
            _("%(value)s is not a positive number."),
            params={"value": value},
            code="positive_required",
        )


def validate_non_negative_decimal(value) -> None:
    """Ensure *value* is zero or greater.

    Accepts ``Decimal``, ``int``, and ``float`` types.
    """
    if value is None:
        return
    try:
        val = Decimal(str(value))
    except Exception as err:
        raise ValidationError(
            _("Value must be a numeric type."),
            code="invalid_numeric",
        ) from err
    if val < Decimal("0"):
        raise ValidationError(
            _("%(value)s is not a non-negative number."),
            params={"value": value},
            code="non_negative_required",
        )


def validate_phone(value: str) -> None:
    """Basic phone number validation.

    Accepts E.164 format (``+1234567890``) or simpler formats
    with digits, spaces, dashes, and parentheses.
    """
    if not value:
        return
    stripped = "".join(c for c in value if c.isdigit())
    if len(stripped) < 7 or len(stripped) > 15:
        raise ValidationError(
            _("Phone number must contain between 7 and 15 digits."),
            code="invalid_phone",
        )


def validate_iso_currency(value: str) -> None:
    """Validate a 3-letter ISO 4217 currency code."""
    if not value:
        return
    if not isinstance(value, str) or len(value) != 3 or not value.isalpha():
        raise ValidationError(
            _("%(value)s is not a valid ISO 4217 currency code."),
            params={"value": value},
            code="invalid_currency",
        )
