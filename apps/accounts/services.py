"""
Service-layer functions for the ``accounts`` app.

Registration and authentication logic lives here, keeping views thin
and making the workflow testable without HTTP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.accounts.models import User


class RegistrationService:
    """Handles new user registration and initial workspace setup.

    ``register_user`` executes a single atomic transaction that:

    1. Creates the ``User``.
    2. Creates the default ``Workspace``.
    3. Creates the ``BusinessProfile``.
    4. Creates the owner's ``WorkspaceMembership``.
    """

    @staticmethod
    def register_user(*, email: str, password: str, **kwargs: Any) -> User:
        """Register a new user and bootstrap their default workspace.

        Executes a single atomic transaction covering **User** creation,
        the default **Workspace** (owned by the user), a **BusinessProfile**,
        and an owner **WorkspaceMembership**.

        Parameters
        ----------
        email:
            The user's email address (used as the login identifier).
        password:
            The user's password (hashed before storage).
        **kwargs:
            Additional fields forwarded to ``User.objects.create_user()``
            (e.g. ``first_name``, ``last_name``, ``username``).
            If ``workspace_name`` is provided it is used as the default
            workspace name; otherwise a name is derived from the email.

        Returns
        -------
        User
            The newly created ``User`` instance.

        Raises
        ------
        IntegrityError
            If a unique constraint is violated (e.g. duplicate email).
        """
        from django.db import transaction
        from django.utils.text import slugify

        from apps.accounts.models import User as UserModel

        from apps.workspaces.models import (
            BusinessProfile,
            Workspace,
            WorkspaceMembership,
        )

        workspace_name = (
            kwargs.pop("workspace_name", None)
            or f"{email.split('@')[0]}'s Workspace"
        )

        with transaction.atomic():
            user = UserModel.objects.create_user(
                email=email,
                password=password,
                **kwargs,
            )

            # Ensure a unique slug for the new workspace.
            max_slug_len = Workspace._meta.get_field("slug").max_length
            base_slug = slugify(workspace_name)[:max_slug_len]
            slug = base_slug
            counter = 1
            while Workspace.objects.filter(slug=slug).exists():
                # Reserve room for "-N" suffix without exceeding max_length.
                suffix = f"-{counter}"
                slug = f"{base_slug[:max_slug_len - len(suffix)]}{suffix}"
                counter += 1

            workspace = Workspace.objects.create(
                owner=user,
                name=workspace_name,
                slug=slug,
            )

            BusinessProfile.objects.create(workspace=workspace)

            WorkspaceMembership.objects.create(
                user=user,
                workspace=workspace,
                role=WorkspaceMembership.Role.OWNER,
            )

        return user


class LoginService:
    """Issues JWT token pairs for authenticated users.

    Token generation is delegated to **SimpleJWT** (``RefreshToken``).
    The caller is responsible for authentication and for passing a
    valid, active ``User`` instance.
    """

    @staticmethod
    def login(user: User) -> dict[str, str]:
        """Generate an access/refresh token pair for the given *user*.

        Parameters
        ----------
        user:
            An already-authenticated ``User`` instance.  No credential
            checking is performed by this method.

        Returns
        -------
        dict[str, str]
            A dictionary with ``"access"`` and ``"refresh"`` token
            strings that the client can use for subsequent requests.
        """
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
