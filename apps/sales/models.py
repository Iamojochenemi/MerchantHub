"""
Sale and SaleItem models for MerchantHub.

Records customer purchases and the line items that compose each sale.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Sale(models.Model):
    """
    Represents a single sale transaction within a workspace.

    Each sale is scoped to a ``Workspace`` and recorded by a ``User``.
    Monetary totals are stored at the sale level for fast aggregation.

    The ``payment_status`` field tracks the lifecycle of the sale
    from creation through to full payment.
    """

    class PaymentStatus(models.TextChoices):
        """Payment status of a sale."""

        PENDING_PAYMENT = "PENDING_PAYMENT", _("Pending Payment")
        PAID = "PAID", _("Paid")
        PARTIALLY_PAID = "PARTIALLY_PAID", _("Partially Paid")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="sales",
        help_text=_("The workspace this sale belongs to."),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales",
        help_text=_("The user who created this sale."),
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING_PAYMENT,
        help_text=_("Whether the sale has been paid for."),
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Sum of line totals before any discounts or taxes."),
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Final amount charged to the customer."),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when the sale was created."),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("Timestamp when the sale was last updated."),
    )

    class Meta:
        db_table = "sales_sale"
        verbose_name = _("Sale")
        verbose_name_plural = _("Sales")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="chk_sales_subtotal_non_negative",
                violation_error_message=_("Subtotal must be greater than or equal to zero."),
            ),
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name="chk_sales_total_non_negative",
                violation_error_message=_("Total must be greater than or equal to zero."),
            ),
        ]
        indexes = [
            models.Index(fields=["workspace"], name="idx_sales_workspace"),
            models.Index(fields=["created_by"], name="idx_sales_created_by"),
            models.Index(fields=["created_at"], name="idx_sales_created_at"),
            models.Index(fields=["payment_status"], name="idx_sales_payment_status"),
            models.Index(
                fields=["workspace", "created_at"],
                name="idx_sales_workspace_created",
            ),
        ]

    def __str__(self) -> str:
        return f"Sale {self.pk} — {self.total} [{self.payment_status}]"

    @property
    def is_paid(self) -> bool:
        """Check if the sale has been fully paid for."""
        return self.payment_status in (self.PaymentStatus.PAID,)


class SaleItem(models.Model):
    """
    A single line item within a sale.

    Each item records the ``product`` sold, the ``quantity``,
    the ``unit_price`` at the time of sale, and the computed
    ``line_total``.  Prices are snapshot at sale time so they
    remain accurate even if the product's price changes later.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="items",
        help_text=_("The sale this item belongs to."),
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="sale_items",
        help_text=_("The product sold. Protected to preserve sale history."),
    )

    quantity = models.PositiveIntegerField(
        help_text=_("Number of units sold. Must be greater than zero."),
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Price per unit at the time of sale."),
    )

    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Computed total for this line item (quantity × unit_price)."),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when the line item was created."),
    )

    class Meta:
        db_table = "sales_sale_item"
        verbose_name = _("Sale Item")
        verbose_name_plural = _("Sale Items")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="chk_sale_items_quantity_positive",
                violation_error_message=_("Quantity must be greater than zero."),
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="chk_sale_items_unit_price_non_negative",
                violation_error_message=_("Unit price must be greater than or equal to zero."),
            ),
            models.CheckConstraint(
                condition=models.Q(line_total__gte=0),
                name="chk_sale_items_line_total_non_negative",
                violation_error_message=_("Line total must be greater than or equal to zero."),
            ),
        ]
        indexes = [
            models.Index(fields=["sale"], name="idx_sale_items_sale"),
            models.Index(fields=["product"], name="idx_sale_items_product"),
            models.Index(
                fields=["sale", "product"],
                name="idx_sale_items_sale_product",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.product} × {self.quantity} @ {self.unit_price}"
        )
