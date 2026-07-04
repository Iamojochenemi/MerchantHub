"""
Serializers for the ``sales`` app.

Keeps validation in the serializer layer and sale creation
delegated to ``SalesService``.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.products.models import Product
from apps.sales.models import Sale, SaleItem


class SaleItemCreateSerializer(serializers.Serializer):
    """Validate a single line-item input for sale creation.

    Accepts ``product`` (UUID) and ``quantity`` (int > 0).
    ``product`` is resolved to a ``Product`` instance during
    validation; workspace ownership is checked by the service layer.
    """

    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        help_text="UUID of the product being sold.",
    )

    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Number of units sold. Must be greater than zero.",
    )


class SaleItemSerializer(serializers.ModelSerializer):
    """Read-only serializer for sale line items.

    Exposes the snapshot of the product sold (``product``),
    ``quantity``, ``unit_price``, and ``line_total``.
    """

    product = serializers.UUIDField(source="product_id", read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            "product",
            "quantity",
            "unit_price",
            "line_total",
        ]
        read_only_fields = fields


class SaleSerializer(serializers.Serializer):
    """Create and represent sales.

    **Input** (write-only):
        ``items`` — list of ``SaleItemCreateSerializer`` dicts.

    **Output** (read-only):
        ``id``, ``subtotal``, ``total``, ``created_at``,
        ``updated_at``, ``items`` (nested ``SaleItemSerializer``).

    ``workspace`` and ``created_by`` are resolved from the
    authenticated request — clients must not provide them.
    """

    id = serializers.UUIDField(read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    total = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    items = SaleItemCreateSerializer(many=True, write_only=True, allow_empty=False)

    def create(self, validated_data: dict[str, Any]) -> Sale:
        """Delegate sale creation to ``SalesService.create_sale``."""
        from apps.sales.services import SalesService
        from apps.workspaces.utils import get_active_workspace

        items_data = validated_data.pop("items")
        request = self.context["request"]
        workspace = get_active_workspace(request)

        # Resolve Product instances from validated PrimaryKeyRelatedField values.
        items = [
            {
                "product": item_data["product"],
                "quantity": item_data["quantity"],
            }
            for item_data in items_data
        ]

        return SalesService.create_sale(
            workspace=workspace,
            created_by=request.user,
            items=items,
        )

    def to_representation(self, instance: Sale) -> dict[str, Any]:
        """Append serialized line items to the sale representation."""
        data = super().to_representation(instance)
        data["items"] = SaleItemSerializer(
            instance.items.all(), many=True
        ).data
        return data
