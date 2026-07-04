"""
Serializers for the ``products`` app.

Keeps validation in the serializer layer and business logic
delegated to ``ProductService``.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.products.models import Product


class ProductSerializer(serializers.ModelSerializer):
    """Validate product data and delegate persistence to ``ProductService``.

    ``workspace`` is **not** exposed to the client — it is resolved
    from the authenticated user's active workspace membership.
    """

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "description",
            "cost_price",
            "selling_price",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate_sku(self, value: str) -> str:
        """Ensure the SKU is unique within the authenticated user's workspace.

        On updates the current instance is excluded from the
        uniqueness check so the product can keep its own SKU.
        """
        from apps.workspaces.utils import get_active_workspace

        request = self.context.get("request")
        if request is None:
            return value

        workspace = get_active_workspace(request)
        qs = Product.objects.filter(workspace=workspace, sku=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A product with this SKU already exists in this workspace."
            )
        return value

    def create(self, validated_data: dict[str, Any]) -> Product:
        """Delegate creation to ``ProductService``."""
        from apps.products.services import ProductService
        from apps.workspaces.utils import get_active_workspace

        request = self.context["request"]
        workspace = get_active_workspace(request)
        return ProductService.create_product(
            workspace=workspace,
            **validated_data,
        )

    def update(
        self, instance: Product, validated_data: dict[str, Any]
    ) -> Product:
        """Delegate update to ``ProductService``."""
        from apps.products.services import ProductService

        return ProductService.update_product(
            instance=instance,
            **validated_data,
        )
