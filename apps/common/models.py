"""
Concrete models for the ``common`` app.

This module re-exports the abstract base models defined in
``base_models.py`` and defines the concrete cross-cutting models:

- ``Notification`` — in-app user notifications.
- ``AuditLog`` — immutable audit trail for state changes.
"""

import uuid

from django.conf import settings
from django.db import models

# Re-export abstract base models for convenience.
from apps.common.base_models import BaseModel, SoftDeleteModel, TimeStampedModel, UUIDModel, WorkspaceScopedModel  # noqa: F401

__all__ = [
    "BaseModel",
    "SoftDeleteModel",
    "TimeStampedModel",
    "UUIDModel",
    "WorkspaceScopedModel",
    "Notification",
    "AuditLog",
]


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------


class Notification(BaseModel):
    """In-app notification sent to a user about a system event."""

    class NotificationType(models.TextChoices):
        LOW_STOCK_ALERT = "low_stock_alert", "Low Stock Alert"
        SALE_COMPLETED = "sale_completed", "Sale Completed"
        STAFF_INVITE = "staff_invite", "Staff Invite"
        PAYMENT_RECEIVED = "payment_received", "Payment Received"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="Recipient of the notification.",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Optional workspace context for the notification.",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        help_text="Category of the notification event.",
    )
    title = models.CharField(max_length=255, help_text="Short notification title.")
    message = models.TextField(help_text="Full notification body.")
    is_read = models.BooleanField(default=False, help_text="Whether the user has read this notification.")
    read_at = models.DateTimeField(null=True, blank=True, help_text="When the user read the notification.")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Auto-delete after this timestamp.")

    class Meta:
        db_table = "common_notification"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=["user"], name="idx_notifications_user"),
            models.Index(fields=["user", "is_read"], name="idx_notifications_user_unread"),
            models.Index(fields=["expires_at"], name="idx_notifications_expires"),
        ]

    def __str__(self) -> str:
        return f"[{self.notification_type}] {self.title}"


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class AuditLog(BaseModel):
    """Immutable record of a significant state change in the system."""

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Workspace context (null for system-wide actions).",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        help_text="User who performed the action.",
    )
    action = models.CharField(
        max_length=50,
        help_text="Machine-readable action identifier, e.g. 'entity.create.product'.",
    )
    target_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Type of the affected entity, e.g. 'product', 'sale'.",
    )
    target_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID of the affected entity.",
    )
    changes = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON object with 'before' and 'after' snapshots.",
    )
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Optional metadata (ip_address, user_agent, correlation_id).",
    )

    # No updated_at — audit logs are immutable once written.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "common_auditlog"
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["workspace"], name="idx_auditlog_workspace"),
            models.Index(fields=["actor"], name="idx_auditlog_actor"),
            models.Index(fields=["target_type", "target_id"], name="idx_auditlog_target"),
            models.Index(fields=["action"], name="idx_auditlog_action"),
            models.Index(fields=["created_at"], name="idx_auditlog_created"),
        ]

    def __str__(self) -> str:
        return f"[{self.action}] {self.actor} @ {self.created_at.isoformat() if self.created_at else 'N/A'}"

    def save(self, *args, **kwargs):
        """Audit logs are append-only — prevent updates."""
        if not self._state.adding:
            raise RuntimeError("AuditLog records are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Audit logs are append-only — prevent deletion."""
        raise RuntimeError("AuditLog records are immutable and cannot be deleted.")
