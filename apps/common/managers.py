"""
Custom querysets and managers for MerchantHub.

Provides reusable query building blocks:

- ``ActiveQuerySet`` — filters out soft-deleted records.
- ``WorkspaceScopedQuerySet`` — adds ``for_workspace()`` filter.
"""

from django.db import models


class ActiveQuerySet(models.QuerySet):
    """Queryset that excludes soft-deleted records by default."""

    def active(self):
        """Return only records that have **not** been soft-deleted."""
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        """Return only records that **have** been soft-deleted."""
        return self.filter(deleted_at__isnull=False)


class WorkspaceScopedQuerySet(ActiveQuerySet):
    """Queryset for models that are scoped to a ``Workspace``."""

    def for_workspace(self, workspace):
        """Filter records that belong to the given *workspace*."""
        return self.filter(workspace=workspace)


class WorkspaceScopedManager(models.Manager):
    """Default manager for ``WorkspaceScopedModel`` subclasses.

    Automatically filters out soft-deleted records and provides
    ``for_workspace()`` for tenant-scoped queries.
    """

    def get_queryset(self):
        return WorkspaceScopedQuerySet(self.model, using=self._db).active()

    def for_workspace(self, workspace):
        return self.get_queryset().for_workspace(workspace)

    def all_with_deleted(self):
        """Return all records including soft-deleted ones."""
        return WorkspaceScopedQuerySet(self.model, using=self._db)

    def deleted_only(self):
        """Return only soft-deleted records."""
        return self.all_with_deleted().deleted()
