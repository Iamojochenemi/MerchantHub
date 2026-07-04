"""
Serializers for the ``inventory`` app.

Keeps validation in the serializer layer and stock mutations
delegated to ``InventoryService``.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.inventory.models import Inventory


class InventorySerializer(serializers.ModelSerializer):
    """Validate inventory data and delegate stock adjustments to ``InventoryService``.

    ``product`` is read-only — inventory records are created automatically
    alongside products and clients may not reassign them.
    """

    class Meta:
        model = Inventory
        fields = [
            "id",
            "product",
            "quantity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "product",
            "created_at",
            "updated_at",
        ]

    def update(
        self, instance: Inventory, validated_data: dict[str, Any]
    ) -> Inventory:
        """Delegate quantity changes to ``InventoryService.adjust_stock``."""
        from apps.inventory.services import InventoryService

        quantity = validated_data.get("quantity")
        if quantity is not None:
            return InventoryService.adjust_stock(
                inventory=instance,
                quantity=quantity,
            )
        return instance
