"""
Customer model for MerchantHub.

Represents a customer of a business (workspace) with contact details
and workspace-level uniqueness constraints for phone numbers.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class Customer(models.Model):
    """
    A person or entity that purchases goods from a workspace.

    Each customer belongs to exactly one workspace for multi-tenant
    isolation. Phone numbers are unique per workspace to prevent
    duplicate contact records.

    .. note::

        Customers are **not** linked to sales yet — the foreign-key
        relationship will be added when the sales module is extended.
        Deleting a customer now does **not** cascade to sales.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for the customer."),
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="customers",
        help_text=_("The workspace this customer belongs to."),
    )

    first_name = models.CharField(
        max_length=150,
        help_text=_("Customer's given name."),
    )

    last_name = models.CharField(
        max_length=150,
        blank=True,
        help_text=_("Customer's family name (optional)."),
    )

    phone_number = models.CharField(
        max_length=30,
        help_text=_("Primary contact phone number. Must be unique per workspace."),
    )

    email = models.EmailField(
        blank=True,
        null=True,
        help_text=_("Optional email address."),
    )

    address = models.TextField(
        blank=True,
        help_text=_("Optional street address or location details."),
    )

    notes = models.TextField(
        blank=True,
        help_text=_("Optional internal notes about the customer."),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("Timestamp when the customer was created."),
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_("Timestamp when the customer was last updated."),
    )

    class Meta:
        db_table = "customers_customer"
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "phone_number"],
                name="uq_customers_workspace_phone",
                violation_error_message=_(
                    "A customer with this phone number already exists "
                    "in this workspace."
                ),
            ),
        ]
        indexes = [
            models.Index(fields=["workspace"], name="idx_customers_workspace"),
            models.Index(fields=["phone_number"], name="idx_customers_phone"),
            models.Index(fields=["email"], name="idx_customers_email"),
        ]

    def __str__(self) -> str:
        """Return the customer's full name, falling back to phone number."""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name
