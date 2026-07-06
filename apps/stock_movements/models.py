"""
StockMovement model for MerchantHub.

Records every inventory change — sales, restocks, and manual adjustments —
to provide a complete audit trail for stock levels.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class StockMovement(models.Model):
    """
    Represents a single change to a product's inventory quantity.

    Every stock mutation through ``InventoryService`` automatically creates
    a ``StockMovement`` record capturing the type of change, the quantity
    involved, the before/after snapshot, and an optional reference and
    actor (``created_by``).
    """

    class MovementType(models.TextChoices):
        SALE = "SALE", _("Sale")
        RESTOCK = "RESTOCK", _("Restock")
        ADJUSTMENT = "ADJUSTMENT", _("Adjustment")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    inventory = models.ForeignKey(
        "inventory.Inventory",
        on_delete=models.CASCADE,
        related_name="stock_movements",
        help_text=_("The inventory record that was changed."),
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
        help_text=_("The type of stock movement: sale, restock, or adjustment."),
    )

    quantity = models.PositiveIntegerField(
        help_text=_("Number of units moved."),
    )

    quantity_before = models.PositiveIntegerField(
        help_text=_("Stock quantity before the movement."),
    )

    quantity_after = models.PositiveIntegerField(
        help_text=_("Stock quantity after the movement."),
    )

    reference = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=_("Optional human-readable reference (e.g. \"Sale #123\", \"PO-001\")."),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("The user who caused the movement. May be null for automated processes."),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when the movement was recorded."),
    )

    class Meta:
        db_table = "stock_movements_stockmovement"
        verbose_name = _("Stock Movement")
        verbose_name_plural = _("Stock Movements")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["inventory"], name="idx_stock_movements_inventory"),
            models.Index(fields=["movement_type"], name="idx_stock_movements_type"),
            models.Index(fields=["created_at"], name="idx_stock_movements_created"),
            models.Index(
                fields=["inventory", "created_at"],
                name="idx_stock_movements_inv_cr",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.get_movement_type_display()} — "
            f"{self.quantity} units "
            f"({self.quantity_before} → {self.quantity_after})"
        )
