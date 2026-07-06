"""
Serializers for the ``stock_movements`` app.

Exposes stock movement records as read-only data for the audit trail.
"""

from rest_framework import serializers

from apps.stock_movements.models import StockMovement


class StockMovementSerializer(serializers.ModelSerializer):
    """Read-only serializer for stock movement records.

    Exposes all fields of a ``StockMovement`` for the audit trail.
    Clients may not create or modify movements directly — they are
    created automatically by ``InventoryService``.
    """

    created_by = serializers.UUIDField(source="created_by_id", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "inventory",
            "movement_type",
            "quantity",
            "quantity_before",
            "quantity_after",
            "reference",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields
