"""
Workspace models for MerchantHub.

Sprint 0 (Foundation) provides a minimal ``Workspace`` model so that
the shared architecture (``WorkspaceScopedModel``, ``WorkspaceMiddleware``,
permission classes) can compile and be tested.

Sprint 1 (Accounts + Workspaces) will expand this module with the full
``Workspace``, ``WorkspaceMembership``, ``BusinessProfile``, ``Role``,
and ``Permission`` models.
"""

import uuid

from django.conf import settings
from django.db import models

from apps.common.base_models import BaseModel, SoftDeleteModel


class Workspace(SoftDeleteModel):
    """A tenant boundary representing one business entity.

    Minimal stub for Sprint 0.  Expanded in Sprint 1 with:
    - ``slug``, ``is_active``
    - Full membership management
    - BusinessProfile, Role, Permission
    """

    name = models.CharField(max_length=255, unique=True, help_text="Business name.")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        help_text="User who created the workspace.",
    )

    class Meta:
        db_table = "workspaces_workspace"
        verbose_name = "Workspace"
        verbose_name_plural = "Workspaces"

    def __str__(self) -> str:
        return self.name
