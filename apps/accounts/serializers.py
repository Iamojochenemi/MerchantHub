"""
Serializers for the ``accounts`` app.

Keeps validation in the serializer layer and business logic
in ``RegistrationService``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rest_framework import serializers

if TYPE_CHECKING:
    from apps.accounts.models import User


class RegistrationSerializer(serializers.Serializer):
    """Validates registration input and delegates creation to the service layer.

    This is intentionally **not** a ``ModelSerializer`` — the creation
    workflow involves multiple models (``User``, ``Workspace``,
    ``BusinessProfile``, ``WorkspaceMembership``) in a single atomic
    transaction managed by ``RegistrationService``.
    """

    email = serializers.EmailField(
        max_length=254,
        help_text="Primary login identifier. Must be unique.",
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
        style={"input_type": "password"},
        help_text="Password — at least 8 characters.",
    )

    first_name = serializers.CharField(
        max_length=150,
        help_text="Given name.",
    )

    last_name = serializers.CharField(
        max_length=150,
        help_text="Family name.",
    )

    workspace_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=False,
        help_text="Optional display name for the default workspace.",
    )

    def validate_email(self, value: str) -> str:
        """Ensure the email address is not already registered."""
        from django.contrib.auth import get_user_model

        UserModel = get_user_model()
        if UserModel.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email address is already registered."
            )
        return UserModel.objects.normalize_email(value.strip())

    def create(self, validated_data: dict[str, Any]) -> User:
        """Delegate all creation logic to the service layer."""
        from apps.accounts.services import RegistrationService

        return RegistrationService.register_user(**validated_data)
