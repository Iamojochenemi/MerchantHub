import uuid

from django.db import models
from django.utils import timezone

from apps.common.managers import WorkspaceScopedManager


class TimeStampedModel(models.Model):
    """
    Abstract base model that adds created_at and updated_at fields.

    - ``created_at`` is set once on creation and never updated.
    - ``updated_at`` is automatically updated on every save.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """
    Abstract base model that uses UUID v4 as primary key.

    UUIDs provide security (non-predictable IDs), distributed-readiness
    (no coordination needed for ID generation), and safe merging.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    """
    Standard base model for all MerchantHub domain entities.

    Composes ``UUIDModel`` (UUID PK) and ``TimeStampedModel``
    (created_at / updated_at).
    """

    class Meta:
        abstract = True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.pk}>"


class SoftDeleteModel(BaseModel):
    """
    Abstract base model that adds soft-delete capability via a ``deleted_at``
    timestamp.  Active records have ``deleted_at IS NULL``; soft-deleted
    records have a non-NULL timestamp indicating when they were deleted.

    Usage
    -----
    Override the default manager to filter out soft-deleted records:

        class MyModel(SoftDeleteModel):
            objects = SoftDeleteManager()

    Call ``instance.delete()`` to soft-delete.
    Call ``instance.hard_delete()`` to permanently remove.
    """

    deleted_at = models.DateTimeField(null=True, blank=True, default=None)

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False) -> tuple:
        """Soft-delete by setting ``deleted_at`` to the current time."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def hard_delete(self, using=None, keep_parents=False) -> tuple:
        """Permanently remove the record from the database."""
        return super().delete(using=using, keep_parents=keep_parents)

    @property
    def is_deleted(self) -> bool:
        """``True`` if this record has been soft-deleted."""
        return self.deleted_at is not None


class WorkspaceScopedModel(SoftDeleteModel):
    """
    Abstract base model that scopes an entity to a ``Workspace`` for
    multi-tenant isolation.

    All workspace-scoped entities inherit from this model and therefore
    carry a ``workspace`` foreign key and soft-delete support.

    The default manager (``objects``) is ``WorkspaceScopedManager``,
    which filters out soft-deleted records and provides a
    ``for_workspace()`` method.
    """

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
        help_text="The workspace this record belongs to.",
    )

    objects = WorkspaceScopedManager()

    class Meta:
        abstract = True
