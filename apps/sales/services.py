"""
Service-layer functions for the ``sales`` app.

Sale creation logic lives here, keeping views thin and making the
workflow testable without HTTP.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from rest_framework.exceptions import ValidationError

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.products.models import Product
    from apps.sales.models import Sale
    from apps.workspaces.models import Workspace


class SalesService:
    """Handles sale creation and lifecycle operations.

    All sale mutations go through this service to ensure consistent
    behaviour (workspace isolation, inventory deduction, atomicity).
    """

    @staticmethod
    def create_sale(
        *,
        workspace: Workspace,
        created_by: User,
        items: list[dict[str, Any]],
    ) -> Sale:
        """Create a sale with line items and deduct inventory atomically.

        Parameters
        ----------
        workspace:
            The workspace the sale belongs to.
        created_by:
            The user who created the sale.
        items:
            A list of item dicts, each containing:

            - ``product`` (:class:`~apps.products.models.Product`)
              The product being sold.
            - ``quantity`` (:class:`int`)
              Number of units sold (must be > 0).

        Returns
        -------
        Sale
            The newly created ``Sale`` instance with its items
            already populated.

        Raises
        ------
        ValidationError
            If any item has a product from a different workspace,
            an invalid quantity, insufficient stock, or no inventory
            record.
        """
        from django.db import transaction

        from apps.inventory.models import Inventory
        from apps.sales.models import Sale, SaleItem

        with transaction.atomic():
            line_totals: list[Decimal] = []

            # Validate items and gather data before creating anything.
            prepared_items: list[dict[str, Any]] = []
            for item_data in items:
                product: Product = item_data["product"]
                quantity: int = item_data["quantity"]

                # --- Workspace check ---
                if product.workspace_id != workspace.pk:
                    raise ValidationError(
                        f"Product '{product.sku}' does not belong to "
                        f"the specified workspace."
                    )

                # --- Quantity check ---
                if not isinstance(quantity, int) or quantity <= 0:
                    raise ValidationError(
                        f"Quantity for '{product.sku}' must be a "
                        f"positive integer, got {quantity}."
                    )

                # --- Inventory check ---
                try:
                    inventory = Inventory.objects.get(product=product)
                except Inventory.DoesNotExist:
                    raise ValidationError(
                        f"No inventory record found for product "
                        f"'{product.sku}'."
                    )

                if inventory.quantity < quantity:
                    raise ValidationError(
                        f"Insufficient stock for '{product.sku}'.  "
                        f"Available: {inventory.quantity}, "
                        f"requested: {quantity}."
                    )

                # --- Read price from DB (never trust the client) ---
                unit_price = Decimal(str(product.selling_price))
                line_total = unit_price * quantity

                line_totals.append(line_total)
                prepared_items.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "line_total": line_total,
                        "_inventory": inventory,
                    }
                )

            # --- Calculate monetary totals ---
            subtotal = sum(line_totals, Decimal("0.00"))
            total = subtotal

            # --- Create the Sale ---
            sale = Sale.objects.create(
                workspace=workspace,
                created_by=created_by,
                payment_status=Sale.PaymentStatus.PENDING_PAYMENT,
                subtotal=subtotal,
                total=total,
            )

            # --- Create SaleItems and deduct inventory ---
            for prep in prepared_items:
                SaleItem.objects.create(
                    sale=sale,
                    product=prep["product"],
                    quantity=prep["quantity"],
                    unit_price=prep["unit_price"],
                    line_total=prep["line_total"],
                )

                from apps.inventory.services import InventoryService

                InventoryService.decrease_stock(
                    inventory=prep["_inventory"],
                    quantity=prep["quantity"],
                )

        return sale
