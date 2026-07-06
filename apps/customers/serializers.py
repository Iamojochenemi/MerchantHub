"""
Serializers for the ``customers`` app.

Keeps validation in the serializer layer and delegates business
logic to ``CustomerService``.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.customers.models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    """Validate customer data and delegate persistence to ``CustomerService``.

    ``workspace`` is **not** exposed to the client — it is resolved
    from the authenticated user's active workspace membership.
    """

    class Meta:
        model = Customer
        fields = [
            "id",
            "first_name",
            "last_name",
            "phone_number",
            "email",
            "address",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_phone_number(self, value: str) -> str:
        """Ensure the phone number is unique within the workspace.

        On updates the current instance is excluded from the
        uniqueness check so the customer can keep its own phone.
        """
        from apps.workspaces.utils import get_active_workspace

        request = self.context.get("request")
        if request is None:
            return value

        workspace = get_active_workspace(request)
        qs = Customer.objects.filter(
            workspace=workspace, phone_number=value
        )
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A customer with this phone number already exists "
                "in this workspace."
            )
        return value

    def create(self, validated_data: dict[str, Any]) -> Customer:
        """Delegate creation to ``CustomerService``."""
        from apps.customers.services import CustomerService
        from apps.workspaces.utils import get_active_workspace

        request = self.context["request"]
        workspace = get_active_workspace(request)
        return CustomerService.create_customer(
            workspace=workspace,
            **validated_data,
        )

    def update(
        self, instance: Customer, validated_data: dict[str, Any]
    ) -> Customer:
        """Delegate update to ``CustomerService``."""
        from apps.customers.services import CustomerService

        return CustomerService.update_customer(
            instance=instance,
            **validated_data,
        )
