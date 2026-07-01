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
