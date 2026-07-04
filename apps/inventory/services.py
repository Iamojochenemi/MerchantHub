"""
Service-layer functions for the ``inventory`` app.

Stock mutations go through this service to enforce business rules
(no negative stock, positive quantity arguments, minimal writes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.exceptions import ValidationError

if TYPE_CHECKING:
    from apps.inventory.models import Inventory


class InventoryService:
    """Handles stock mutations for product inventory.

    All stock changes must go through this service to ensure
    business rules are enforced consistently:

    - Quantity arguments must be positive integers.
    - Stock can never become negative.
    - Only the fields that changed are written to the database.
    """

    @staticmethod
    def increase_stock(*, inventory: Inventory, quantity: int) -> Inventory:
        """Add *quantity* units to the inventory.

        Parameters
        ----------
        inventory:
            The inventory record to update.
        quantity:
            Number of units to add.  Must be a positive integer.

        Returns
        -------
        Inventory
            The updated inventory instance (same object).

        Raises
        ------
        ValidationError
            If *quantity* is not a positive integer.
        """
        InventoryService._validate_quantity(quantity)

        inventory.quantity += quantity
        inventory.save(update_fields=["quantity", "updated_at"])
        return inventory

    @staticmethod
    def decrease_stock(*, inventory: Inventory, quantity: int) -> Inventory:
        """Remove *quantity* units from the inventory.

        Parameters
        ----------
        inventory:
            The inventory record to update.
        quantity:
            Number of units to remove.  Must be a positive integer.

        Returns
        -------
        Inventory
            The updated inventory instance (same object).

        Raises
        ------
        ValidationError
            If *quantity* is not a positive integer, or if the
            inventory does not have enough stock.
        """
        InventoryService._validate_quantity(quantity)

        if inventory.quantity < quantity:
            raise ValidationError({
                "quantity": (
                    f"Insufficient stock.  Available: {inventory.quantity}, "
                    f"requested: {quantity}."
                ),
            })

        inventory.quantity -= quantity
        inventory.save(update_fields=["quantity", "updated_at"])
        return inventory

    @staticmethod
    def adjust_stock(*, inventory: Inventory, quantity: int) -> Inventory:
        """Set the inventory to an exact *quantity* value.

        This is an absolute override — the inventory quantity is
        set to *quantity* regardless of its current value.

        Parameters
        ----------
        inventory:
            The inventory record to update.
        quantity:
            The new stock quantity.  Must be a non-negative integer.

        Returns
        -------
        Inventory
            The updated inventory instance (same object).

        Raises
        ------
        ValidationError
            If *quantity* is not a non-negative integer.
        """
        if not isinstance(quantity, int) or quantity < 0:
            raise ValidationError({
                "quantity": (
                    "Adjustment quantity must be a non-negative integer, "
                    f"got {quantity}."
                ),
            })

        inventory.quantity = quantity
        inventory.save(update_fields=["quantity", "updated_at"])
        return inventory

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        """Ensure *quantity* is a positive integer.

        Raises
        ------
        ValidationError
            If *quantity* is not a positive integer.
        """
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValidationError({
                "quantity": f"Quantity must be a positive integer, got {quantity}.",
            })
