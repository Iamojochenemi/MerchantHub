"""
Serializers for the ``accounts`` app.

Keeps validation in the serializer layer and business logic
in ``RegistrationService``.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

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


class LoginSerializer(serializers.Serializer):
    """Validates login credentials and returns the authenticated user.

    Authentication is performed via ``django.contrib.auth.authenticate``
    using ``email`` as the username field.  On success the ``User``
    instance is stored in ``validated_data["user"]`` for downstream
    consumers (e.g. a view that issues a JWT token pair).
    """

    email = serializers.EmailField(
        help_text="Registered email address.",
    )

    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        help_text="Account password.",
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Authenticate the user and store the result on *attrs*."""
        from django.contrib.auth import authenticate, get_user_model

        # Look up the user by normalized email so we can distinguish
        # "not found" from "disabled" without relying on authenticate().
        UserModel = get_user_model()
        normalized_email = UserModel.objects.normalize_email(attrs["email"])

        try:
            user = UserModel.objects.get(email__iexact=normalized_email)
        except UserModel.DoesNotExist:
            user = None

        if user is not None and not user.is_active:
            raise serializers.ValidationError(
                "This account has been disabled."
            )

        authenticated_user = authenticate(
            request=self.context.get("request"),
            username=normalized_email,
            password=attrs["password"],
        )

        if authenticated_user is None:
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        attrs["user"] = authenticated_user
        return attrs


class CurrentUserSerializer(serializers.ModelSerializer):
    """Read-only serializer for the currently authenticated user.

    Includes basic profile fields plus a summary of the user's owned
    workspace (``id``, ``name``, ``slug``) and their role within it.
    """

    workspace = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "workspace",
            "role",
        ]
        read_only_fields = fields

    def get_workspace(self, obj: User) -> dict[str, str] | None:
        """Return a summary of the user's owned workspace, or *None*."""
        from apps.workspaces.models import Workspace

        try:
            workspace = obj.owned_workspaces.get()
        except Workspace.DoesNotExist:
            return None
        return {
            "id": str(workspace.id),
            "name": workspace.name,
            "slug": workspace.slug,
        }

    def get_role(self, obj: User) -> str | None:
        """Return the user's role in their owned workspace, or *None*."""
        from apps.workspaces.models import Workspace, WorkspaceMembership

        try:
            workspace = obj.owned_workspaces.get()
        except Workspace.DoesNotExist:
            return None
        try:
            membership = workspace.memberships.get(user=obj)
        except WorkspaceMembership.DoesNotExist:
            return None
        return membership.role
