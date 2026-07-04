"""
Product model for MerchantHub.

Defines products that belong to a workspace for multi-tenant isolation.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class Product(models.Model):
    """
    Represents a product sold by a business (workspace).

    Each product belongs to exactly one workspace. SKU uniqueness is
    enforced per workspace via a database constraint. Inventory and
    stock levels are managed by the separate ``inventory`` app.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="products",
        help_text=_("The workspace this product belongs to."),
    )

    name = models.CharField(
        max_length=255,
        help_text=_("Product name displayed on invoices, receipts, and reports."),
    )

    sku = models.CharField(
        max_length=100,
        help_text=_("Stock-keeping unit identifier. Must be unique per workspace."),
    )

    description = models.TextField(
        blank=True,
        help_text=_("Optional product description or notes."),
    )

    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Purchase cost of the product (before markup)."),
    )

    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Price charged to the customer."),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Designates whether this product is available for sale."),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when the product was created."),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("Timestamp when the product was last updated."),
    )

    class Meta:
        db_table = "products_product"
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "sku"],
                name="uq_products_workspace_sku",
                violation_error_message=_(
                    "A product with this SKU already exists in this workspace."
                ),
            ),
            models.CheckConstraint(
                condition=models.Q(cost_price__gte=0),
                name="chk_products_cost_price_non_negative",
                violation_error_message=_("Cost price must be greater than or equal to zero."),
            ),
            models.CheckConstraint(
                condition=models.Q(selling_price__gt=0),
                name="chk_products_selling_price_positive",
                violation_error_message=_("Selling price must be greater than zero."),
            ),
        ]
        indexes = [
            models.Index(fields=["workspace"], name="idx_products_workspace"),
            models.Index(fields=["sku"], name="idx_products_sku"),
            models.Index(fields=["is_active"], name="idx_products_is_active"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"
