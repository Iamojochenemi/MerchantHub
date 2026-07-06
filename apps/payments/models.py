"""
Payment model for MerchantHub.

Records every payment received for a sale. Designed so that
integrating Nomba (or any other PSP) later only requires calling
``PaymentService.update_payment_status()`` after a successful
verification callback.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Payment(models.Model):
    """
    Represents a single payment received for a sale.

    Each payment is scoped to a ``Workspace`` and linked to a ``Sale``.
    A customer may optionally be attached for customer-account tracking.

    Only **one** ``Payment`` with ``status=SUCCESS`` is allowed per
    ``Sale`` — enforced via a partial unique index at the database
    level and a complementary check in ``PaymentService``.
    """

    class PaymentMethod(models.TextChoices):
        """Supported payment methods."""

        CASH = "CASH", _("Cash")
        TRANSFER = "TRANSFER", _("Bank Transfer")
        CARD = "CARD", _("Card Payment")
        POS = "POS", _("POS Terminal")
        OTHER = "OTHER", _("Other")

    class Status(models.TextChoices):
        """Possible payment statuses."""

        PENDING = "PENDING", _("Pending")
        SUCCESS = "SUCCESS", _("Success")
        FAILED = "FAILED", _("Failed")
        REFUNDED = "REFUNDED", _("Refunded")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for the payment."),
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="payments",
        help_text=_("The workspace this payment belongs to."),
    )

    sale = models.ForeignKey(
        "sales.Sale",
        on_delete=models.PROTECT,
        related_name="payments",
        help_text=_("The sale this payment is for. Protected to preserve payment history."),
    )

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        help_text=_("Optional customer who made the payment."),
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Payment amount. Must be a positive value."),
    )

    currency = models.CharField(
        max_length=3,
        default="NGN",
        help_text=_("ISO-4217 currency code (e.g. NGN, USD)."),
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        help_text=_("How the payment was made."),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_("Current payment status."),
    )

    provider_reference = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=_(
            "External reference from the payment provider "
            "(e.g. Nomba transaction ID)."
        ),
    )

    external_reference = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Internal reference for the payment (e.g. receipt number)."),
    )

    notes = models.TextField(
        blank=True,
        help_text=_("Optional notes about the payment."),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when the payment was created."),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("Timestamp when the payment was last updated."),
    )

    class Meta:
        db_table = "payments_payment"
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="chk_payments_amount_positive",
                violation_error_message=_(
                    "Payment amount must be greater than zero."
                ),
            ),
            models.UniqueConstraint(
                fields=["sale"],
                condition=models.Q(status="SUCCESS"),
                name="uq_payments_single_success_per_sale",
                violation_error_message=_(
                    "A successful payment already exists for this sale."
                ),
            ),
        ]
        indexes = [
            models.Index(fields=["workspace"], name="idx_payments_workspace"),
            models.Index(fields=["sale"], name="idx_payments_sale"),
            models.Index(fields=["status"], name="idx_payments_status"),
            models.Index(
                fields=["provider_reference"],
                name="idx_payments_provider_ref",
            ),
            models.Index(
                fields=["workspace", "created_at"],
                name="idx_payments_ws_created",
            ),
        ]

    def __str__(self) -> str:
        """Return a human-readable payment summary."""
        return (
            f"Payment {self.pk} — {self.amount} {self.currency} "
            f"[{self.status}]"
        )
