"""
Service-layer functions for the ``payments`` app.

All payment mutations go through this service to enforce business
rules (positive amount, workspace consistency, single-success-per-sale).

Designed so that integrating Nomba later only requires calling
``update_payment_status()`` after a successful verification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

if TYPE_CHECKING:
    from uuid import UUID

    from apps.accounts.models import User
    from apps.payments.models import Payment
    from apps.workspaces.models import Workspace


class PaymentService:
    """Handles payment lifecycle operations.

    All payment mutations go through this service to ensure
    consistent behaviour:

    - Workspace and sale consistency
    - Single ``SUCCESS`` payment per sale
    - Positive amount enforcement
    - Safe status transitions (PENDING → SUCCESS/FAILED, SUCCESS → REFUNDED)
    """

    @staticmethod
    def create_payment(
        *,
        workspace: Workspace,
        sale,
        amount,
        payment_method: str,
        currency: str = "NGN",
        customer=None,
        status: str = "PENDING",
        provider_reference: str | None = None,
        external_reference: str | None = None,
        notes: str = "",
    ) -> Payment:
        """Record a new payment for a sale.

        Parameters
        ----------
        workspace:
            The workspace the payment belongs to.
        sale:
            The ``Sale`` instance being paid for.
        amount:
            Payment amount (must be positive).
        payment_method:
            One of ``Payment.PaymentMethod`` values.
        currency:
            ISO-4217 currency code (default ``"NGN"``).
        customer:
            Optional ``Customer`` instance who made the payment.
        status:
            Initial payment status (default ``"PENDING"``).
        provider_reference:
            Optional external PSP reference (populated by Nomba later).
        external_reference:
            Optional internal reference (e.g. receipt number).
        notes:
            Optional payment notes.

        Returns
        -------
        Payment
            The newly created ``Payment`` instance.

        Raises
        ------
        ValidationError
            If the amount is not positive, if the sale belongs to a
            different workspace, if the customer belongs to a different
            workspace, or if a ``SUCCESS`` payment already exists for
            this sale.
        """
        from apps.payments.models import Payment

        with transaction.atomic():
            # --- Workspace consistency ---
            if sale.workspace_id != workspace.pk:
                raise ValidationError(
                    "The sale does not belong to the specified workspace."
                )

            # --- Customer workspace consistency ---
            if customer is not None and customer.workspace_id != workspace.pk:
                raise ValidationError(
                    "The customer does not belong to the specified workspace."
                )

            # --- Amount must be positive ---
            if amount is None or amount <= 0:
                raise ValidationError(
                    "Payment amount must be positive."
                )

            # --- Single SUCCESS per sale ---
            if status == "SUCCESS":
                PaymentService._ensure_no_successful_payment(sale.pk)

            payment = Payment.objects.create(
                workspace=workspace,
                sale=sale,
                customer=customer,
                amount=amount,
                currency=currency,
                payment_method=payment_method,
                status=status,
                provider_reference=provider_reference,
                external_reference=external_reference,
                notes=notes,
            )
        return payment

    @staticmethod
    def update_payment_status(
        *,
        payment: Payment,
        new_status: str,
    ) -> Payment:
        """Update the status of an existing payment.

        This is the method that Nomba integration will call after
        a successful or failed payment verification.

        Valid transitions:

        - ``PENDING`` → ``SUCCESS`` / ``FAILED``
        - ``SUCCESS`` → ``REFUNDED``
        - ``FAILED`` → ``SUCCESS``

        Parameters
        ----------
        payment:
            The ``Payment`` instance to update.
        new_status:
            The new status value.

        Returns
        -------
        Payment
            The updated ``Payment`` instance (same object).

        Raises
        ------
        ValidationError
            If the transition is not allowed.
        """
        from apps.payments.models import Payment

        with transaction.atomic():
            allowed_transitions = {
                Payment.Status.PENDING: [
                    Payment.Status.SUCCESS,
                    Payment.Status.FAILED,
                ],
                Payment.Status.SUCCESS: [Payment.Status.REFUNDED],
                Payment.Status.FAILED: [Payment.Status.SUCCESS],
            }

            allowed_next = allowed_transitions.get(payment.status, [])

            if new_status not in allowed_next:
                raise ValidationError(
                    f"Cannot transition from {payment.status} to {new_status}. "
                    f"Allowed transitions from {payment.status}: "
                    f"{[s.value for s in allowed_next]}."
                )

            # --- Enforce single SUCCESS per sale ---
            if new_status == "SUCCESS":
                PaymentService._ensure_no_successful_payment(
                    payment.sale_id,
                    exclude_pk=payment.pk,
                )

            payment.status = new_status
            payment.save(update_fields=["status", "updated_at"])
        return payment

    @staticmethod
    def refund_payment(
        *,
        payment: Payment,
    ) -> Payment:
        """Convenience wrapper to mark a payment as refunded.

        This calls ``update_payment_status()`` with ``"REFUNDED"``.

        Parameters
        ----------
        payment:
            The ``Payment`` instance to refund.

        Returns
        -------
        Payment
            The updated ``Payment`` instance.

        Raises
        ------
        ValidationError
            If the payment is not in ``SUCCESS`` status.
        """
        return PaymentService.update_payment_status(
            payment=payment,
            new_status="REFUNDED",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_no_successful_payment(
        sale_id: UUID,
        exclude_pk: UUID | None = None,
    ) -> None:
        """Ensure no ``SUCCESS`` payment exists for the given sale.

        Parameters
        ----------
        sale_id:
            The sale's UUID to check.
        exclude_pk:
            Optional payment PK to exclude from the check (used
            during status updates to avoid self-conflict).

        Raises
        ------
        ValidationError
            If a ``SUCCESS`` payment already exists for this sale.
        """
        from apps.payments.models import Payment

        qs = Payment.objects.filter(
            sale_id=sale_id,
            status=Payment.Status.SUCCESS,
        )
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)

        if qs.exists():
            raise ValidationError(
                "A successful payment already exists for this sale."
            )
