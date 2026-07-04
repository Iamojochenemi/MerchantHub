"""
Inventory model for MerchantHub.

Tracks stock quantities for products. Each product has exactly one
inventory record via a one-to-one relationship.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class Inventory(models.Model):
    """
    Represents the stock level of a product.

    Each product can have only one inventory record enforced by a
    ``OneToOneField``. Quantity can never be negative (enforced by a
    database ``CheckConstraint``).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    product = models.OneToOneField(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="inventory",
        help_text=_("The product this inventory record belongs to."),
    )

    quantity = models.PositiveIntegerField(
        default=0,
        help_text=_("Current stock quantity. Cannot be negative."),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when the inventory record was created."),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("Timestamp when the inventory record was last updated."),
    )

    class Meta:
        db_table = "inventory_inventory"
        verbose_name = _("Inventory")
        verbose_name_plural = _("Inventory")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="chk_inventory_quantity_non_negative",
                violation_error_message=_("Quantity cannot be negative."),
            ),
        ]
        indexes = [
            models.Index(fields=["product"], name="idx_inventory_product"),
        ]

    def __str__(self) -> str:
        return f"{self.product} — {self.quantity} in stock"
