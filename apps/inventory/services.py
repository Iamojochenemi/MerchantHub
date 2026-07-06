"""
Service-layer functions for the ``inventory`` app.

Stock mutations go through this service to enforce business rules
(no negative stock, positive quantity arguments, minimal writes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.exceptions import ValidationError

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.inventory.models import Inventory


class InventoryService:
    """Handles stock mutations for product inventory.

    All stock changes must go through this service to ensure
    business rules are enforced consistently:

    - Quantity arguments must be positive integers.
    - Stock can never become negative.
    - Only the fields that changed are written to the database.
    - Every mutation automatically creates a ``StockMovement`` record
      for the audit trail.
    """

    @staticmethod
    def increase_stock(
        *,
        inventory: Inventory,
        quantity: int,
        created_by: User | None = None,
        reference: str = "",
    ) -> Inventory:
        """Add *quantity* units to the inventory.

        Parameters
        ----------
        inventory:
            The inventory record to update.
        quantity:
            Number of units to add.  Must be a positive integer.
        created_by:
            Optional user who performed the restock.
        reference:
            Optional human-readable reference (e.g. ``"PO-001"``).

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

        quantity_before = inventory.quantity
        inventory.quantity += quantity
        inventory.save(update_fields=["quantity", "updated_at"])

        InventoryService._record_movement(
            inventory=inventory,
            movement_type="RESTOCK",
            quantity=quantity,
            quantity_before=quantity_before,
            quantity_after=inventory.quantity,
            created_by=created_by,
            reference=reference,
        )

        return inventory

    @staticmethod
    def decrease_stock(
        *,
        inventory: Inventory,
        quantity: int,
        created_by: User | None = None,
        reference: str = "",
    ) -> Inventory:
        """Remove *quantity* units from the inventory.

        Parameters
        ----------
        inventory:
            The inventory record to update.
        quantity:
            Number of units to remove.  Must be a positive integer.
        created_by:
            Optional user who performed the deduction.
        reference:
            Optional human-readable reference (e.g. ``"Sale #123"``).

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

        quantity_before = inventory.quantity
        inventory.quantity -= quantity
        inventory.save(update_fields=["quantity", "updated_at"])

        InventoryService._record_movement(
            inventory=inventory,
            movement_type="SALE",
            quantity=quantity,
            quantity_before=quantity_before,
            quantity_after=inventory.quantity,
            created_by=created_by,
            reference=reference,
        )

        return inventory

    @staticmethod
    def adjust_stock(
        *,
        inventory: Inventory,
        quantity: int,
        created_by: User | None = None,
        reference: str = "",
    ) -> Inventory:
        """Set the inventory to an exact *quantity* value.

        This is an absolute override — the inventory quantity is
        set to *quantity* regardless of its current value.

        Parameters
        ----------
        inventory:
            The inventory record to update.
        quantity:
            The new stock quantity.  Must be a non-negative integer.
        created_by:
            Optional user who performed the adjustment.
        reference:
            Optional human-readable reference (e.g. ``"Manual adjustment"``).

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

        quantity_before = inventory.quantity
        inventory.quantity = quantity
        inventory.save(update_fields=["quantity", "updated_at"])

        InventoryService._record_movement(
            inventory=inventory,
            movement_type="ADJUSTMENT",
            quantity=quantity,
            quantity_before=quantity_before,
            quantity_after=inventory.quantity,
            created_by=created_by,
            reference=reference,
        )

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

    @staticmethod
    def _record_movement(
        *,
        inventory: Inventory,
        movement_type: str,
        quantity: int,
        quantity_before: int,
        quantity_after: int,
        created_by: User | None = None,
        reference: str = "",
    ) -> None:
        """Persist a ``StockMovement`` record for the audit trail."""
        from apps.stock_movements.models import StockMovement

        StockMovement.objects.create(
            inventory=inventory,
            movement_type=movement_type,
            quantity=quantity,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            reference=reference,
            created_by=created_by,
        )
