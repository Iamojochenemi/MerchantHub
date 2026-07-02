"""
Workspace model for MerchantHub.

Defines the multi-tenant boundary: all domain data (products, sales,
customers, expenses, payments) is scoped within a ``Workspace``.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Workspace(models.Model):
    """
    A tenant boundary representing one business entity.

    All domain data (products, sales, customers, expenses, payments)
    is scoped within a ``Workspace`` for multi-tenant isolation.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_workspaces",
        help_text=_("User who created and owns this workspace."),
    )

    name = models.CharField(
        max_length=255,
        help_text=_("Business name displayed across the platform."),
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text=_("URL-friendly identifier for the workspace."),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Designates whether this workspace is active and accessible."),
    )

    created_at = models.DateTimeField(auto_now_add=True, help_text=_("Timestamp when the workspace was created."))
    updated_at = models.DateTimeField(auto_now=True, help_text=_("Timestamp when the workspace was last updated."))

    class Meta:
        db_table = "workspaces_workspace"
        verbose_name = _("Workspace")
        verbose_name_plural = _("Workspaces")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["owner"], name="idx_workspaces_owner"),
            models.Index(fields=["slug"], name="idx_workspaces_slug"),
            models.Index(fields=["is_active"], name="idx_workspaces_is_active"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="uq_workspaces_owner_name",
                violation_error_message=_("You already have a workspace with this name."),
            ),
        ]

    def __str__(self) -> str:
        return self.name


class BusinessProfile(models.Model):
    """
    Stores business-specific metadata for a workspace.

    This is a 1:1 extension of ``Workspace`` holding legal, tax,
    contact, and localization information.  It is created and
    managed alongside its workspace (no independent lifecycle).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    workspace = models.OneToOneField(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="business_profile",
        help_text=_("The workspace this profile belongs to."),
    )

    legal_name = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Registered business name (if different from workspace name)."),
    )
    tax_id = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Tax registration number (VAT, EIN, etc.)."),
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text=_("Business contact phone number."),
    )
    email = models.EmailField(
        blank=True,
        help_text=_("Business contact email address."),
    )
    address = models.TextField(
        blank=True,
        help_text=_("Business physical address."),
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
        help_text=_("ISO 4217 currency code for the workspace."),
    )
    timezone = models.CharField(
        max_length=64,
        default="UTC",
        help_text=_("IANA timezone identifier for the workspace."),
    )
    logo = models.ImageField(
        upload_to="business_logos/",
        blank=True,
        null=True,
        help_text=_("Business logo image."),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when the profile was created."),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("Timestamp when the profile was last updated."),
    )

    class Meta:
        db_table = "workspaces_business_profile"
        verbose_name = _("Business Profile")
        verbose_name_plural = _("Business Profiles")

    def __str__(self) -> str:
        return f"{self.workspace.name} Business Profile"


class WorkspaceMembership(models.Model):
    """
    Links a user to a workspace with a specific role.

    Enforces the many-to-many relationship between users and workspaces:
    each user can belong to multiple workspaces, and each workspace can
    have multiple members. A user cannot hold more than one membership
    in the same workspace (enforced by a unique constraint).
    """

    class Role(models.TextChoices):
        """Available roles within a workspace."""

        OWNER = "owner", _("Owner")
        MANAGER = "manager", _("Manager")
        STAFF = "staff", _("Staff")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_memberships",
        help_text=_("The user who is a member of the workspace."),
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="memberships",
        help_text=_("The workspace the user belongs to."),
    )

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        help_text=_("Role assigned to the user within this workspace."),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Designates whether this membership is active and the user can access the workspace."),
    )

    joined_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when the user joined the workspace."),
    )

    class Meta:
        db_table = "workspaces_workspace_membership"
        verbose_name = _("Workspace Membership")
        verbose_name_plural = _("Workspace Memberships")
        indexes = [
            models.Index(fields=["workspace", "role"], name="idx_ws_membership_ws_role"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "workspace"],
                name="uq_ws_membership_user_workspace",
                violation_error_message=_("This user is already a member of this workspace."),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} — {self.workspace.name} ({self.get_role_display()})"
