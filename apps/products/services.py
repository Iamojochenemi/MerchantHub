"""
Service-layer functions for the ``products`` app.

Keeps business logic out of views and serialisers, making the
workflow testable without HTTP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.products.models import Product
    from apps.workspaces.models import Workspace


class ProductService:
    """Handles product lifecycle operations.

    All product mutations go through this service to ensure
    consistent behaviour (soft-delete enforcement, workspace
    scoping, audit trail hooks for future use).
    """

    @staticmethod
    def create_product(
        *, workspace: Workspace, **validated_data: Any
    ) -> Product:
        """Create a new product scoped to *workspace*.

        Parameters
        ----------
        workspace:
            The workspace the product belongs to.
        **validated_data:
            Pre-validated field values (``name``, ``sku``,
            ``description``, ``cost_price``, ``selling_price``).

        Returns
        -------
        Product
            The newly created ``Product`` instance.
        """
        from apps.products.models import Product

        product = Product.objects.create(
            workspace=workspace,
            **validated_data,
        )
        return product

    @staticmethod
    def update_product(
        *, instance: Product, **validated_data: Any
    ) -> Product:
        """Update an existing product in-place.

        Parameters
        ----------
        instance:
            The product to update.
        **validated_data:
            Pre-validated field values to apply.

        Returns
        -------
        Product
            The updated ``Product`` instance (same object).
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    def archive_product(*, instance: Product) -> Product:
        """Soft-delete a product by setting ``is_active`` to ``False``.

        This is the **only** deletion mechanism — products are
        never hard-deleted through the API.

        Parameters
        ----------
        instance:
            The product to archive.

        Returns
        -------
        Product
            The archived ``Product`` instance.
        """
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        return instance
