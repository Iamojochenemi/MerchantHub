"""
Serializers for the ``payments`` app.

Keeps validation in the serializer layer and delegates business
logic to ``PaymentService``.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.payments.models import Payment
from apps.sales.models import Sale
from apps.customers.models import Customer


class PaymentSerializer(serializers.ModelSerializer):
    """Validate payment data and delegate persistence to ``PaymentService``.

    ``workspace`` is **not** exposed to the client — it is resolved
    from the authenticated user's active workspace membership.

    The serializer enforces:

    - Sale belongs to the same workspace as the authenticated user.
    - Customer (if supplied) belongs to the same workspace as the sale.
    - Amount is positive.
    """

    class Meta:
        model = Payment
        fields = [
            "id",
            "sale",
            "customer",
            "amount",
            "currency",
            "payment_method",
            "status",
            "provider_reference",
            "external_reference",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "status": {"required": False},
            "currency": {"required": False},
        }

    def validate_sale(self, value: Sale) -> Sale:
        """Ensure the sale belongs to the authenticated user's workspace."""
        from apps.workspaces.utils import get_active_workspace

        request = self.context.get("request")
        if request is None:
            return value

        workspace = get_active_workspace(request)
        if value.workspace_id != workspace.pk:
            raise serializers.ValidationError(
                "This sale does not belong to your workspace."
            )
        return value

    def validate_customer(self, value: Customer | None) -> Customer | None:
        """Ensure the customer (if supplied) belongs to the same workspace."""
        if value is None:
            return value

        from apps.workspaces.utils import get_active_workspace

        request = self.context.get("request")
        if request is None:
            return value

        workspace = get_active_workspace(request)
        if value.workspace_id != workspace.pk:
            raise serializers.ValidationError(
                "This customer does not belong to your workspace."
            )
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Cross-field validation for amount."""
        amount = attrs.get("amount")
        if amount is not None and amount <= 0:
            raise serializers.ValidationError(
                {"amount": "Payment amount must be positive."}
            )
        return attrs

    def create(self, validated_data: dict[str, Any]) -> Payment:
        """Delegate creation to ``PaymentService``."""
        from apps.payments.services import PaymentService
        from apps.workspaces.utils import get_active_workspace

        request = self.context["request"]
        workspace = get_active_workspace(request)

        return PaymentService.create_payment(
            workspace=workspace,
            **validated_data,
        )

    def update(
        self, instance: Payment, validated_data: dict[str, Any]
    ) -> Payment:
        """Update payment fields in-place.

        Status changes are forwarded to ``PaymentService`` for
        transition validation; other fields are applied directly.
        """
        from apps.payments.services import PaymentService

        # If status is being updated, use the service.
        new_status = validated_data.pop("status", None)
        if new_status is not None and new_status != instance.status:
            instance = PaymentService.update_payment_status(
                payment=instance,
                new_status=new_status,
            )

        # Apply remaining field updates.
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if validated_data:
            instance.save()

        return instance
