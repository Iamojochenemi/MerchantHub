"""Add WebhookEvent model and unique constraint on provider_reference."""
from __future__ import annotations

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    """Add WebhookEvent model and conditional unique index on provider_reference."""

    dependencies = [
        ("payments", "0002_payment_uq_payments_single_success_per_sale"),
    ]

    operations = [
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        help_text="Unique identifier for this webhook event record.",
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        max_length=50,
                        help_text="Payment provider name (e.g. 'nomba').",
                    ),
                ),
                (
                    "event_id",
                    models.CharField(
                        max_length=255,
                        unique=True,
                        help_text="Unique event identifier from the provider. Used for idempotency.",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        max_length=100,
                        blank=True,
                        help_text="The webhook event type (e.g. 'checkout.completed').",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=50,
                        blank=True,
                        help_text="Processing status (e.g. 'processed', 'skipped').",
                    ),
                ),
                (
                    "payload",
                    models.JSONField(
                        default=dict,
                        blank=True,
                        help_text="The raw webhook payload for audit/debugging.",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this event was processed.",
                    ),
                ),
            ],
            options={
                "db_table": "payments_webhook_event",
                "verbose_name": "Webhook Event",
                "verbose_name_plural": "Webhook Events",
                "ordering": ["-created_at"],
            },
        ),
        # Add a partial unique index on provider_reference for non-null values.
        # This prevents duplicate provider references while allowing multiple
        # NULL values (for cash payments that lack a provider reference).
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                fields=["provider_reference"],
                name="uq_payments_provider_reference",
                condition=models.Q(("provider_reference__isnull", False)),
                violation_error_message=(
                    "A payment with this provider reference already exists."
                ),
            ),
        ),
    ]
