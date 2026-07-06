"""
Payment orchestration service connecting Nomba checkout to MerchantHub models.

Provides :class:`NombaPaymentService` which coordinates the Nomba
checkout API with MerchantHub's ``Sale`` and ``Payment`` models,
and :class:`NombaCheckoutInitResult` which encapsulates the outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.payments.integrations.nomba.auth import NombaAuthService
from apps.payments.integrations.nomba.checkout import NombaCheckoutService
from apps.payments.integrations.nomba.verification import (
    NombaTransactionService,
)
from apps.payments.services import PaymentService


@dataclass(frozen=True)
class NombaCheckoutInitResult:
    """The result of initiating a Nomba checkout for a sale.

    Parameters
    ----------
    checkout_link:
        The URL to redirect the customer to for payment completion.
    order_reference:
        The Nomba order reference (also stored as
        ``payment.provider_reference``).
    payment_id:
        The UUID of the newly created ``Payment`` record.
    sale_id:
        The UUID of the ``Sale`` being paid for.
    """

    checkout_link: str
    order_reference: str
    payment_id: str
    sale_id: str


@dataclass(frozen=True)
class PaymentVerificationResult:
    """The result of verifying and updating a payment.

    Parameters
    ----------
    payment_id:
        The UUID of the ``Payment`` that was updated.
    sale_id:
        The UUID of the ``Sale`` associated with the payment.
    old_status:
        The payment status before the update.
    new_status:
        The payment status after the update.
    sale_payment_status:
        The updated payment status on the ``Sale`` (e.g. ``"PAID"``).
    nomba_status:
        The raw status from Nomba's verification response.
    """

    payment_id: str
    sale_id: str
    old_status: str
    new_status: str
    sale_payment_status: str
    nomba_status: str


class NombaPaymentService:
    """Orchestrate Nomba checkout creation and payment recording.

    This service connects the Nomba API layer to MerchantHub's domain
    models — every checkout order created on Nomba also creates a
    ``Payment`` record in the local database so that petty traders
    can track all transactions in one place.

    Usage::

        from apps.payments.integrations.nomba import NombaPaymentService

        result = NombaPaymentService.initiate_checkout(
            sale=sale_instance,
            callback_url="https://merchanthub.example.com/callback",
        )
        print(f"Send customer to: {result.checkout_link}")
    """

    @staticmethod
    def initiate_checkout(
        *,
        sale,
        callback_url: str | None = None,
        customer_email: str | None = None,
        metadata: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> NombaCheckoutInitResult:
        """Create a Nomba checkout order and record a pending Payment.

        This method:

        1. Obtains a fresh Nomba OAuth access token (or uses the one
           provided via ``access_token``).
        2. Creates a checkout order on Nomba with the sale's total
           amount.
        3. Records a **PENDING** ``Payment`` in MerchantHub linked to
           the sale, with the Nomba ``orderReference`` stored as
           ``provider_reference``.

        When Nomba confirms payment via webhook, the ``Payment``
        status should be updated via :meth:`verify_and_update_payment`.

        Parameters
        ----------
        sale:
            The ``Sale`` instance to generate a checkout for.
        callback_url:
            Optional URL Nomba redirects the customer to after
            payment.
        customer_email:
            Optional customer email for receipt delivery.
        metadata:
            Optional arbitrary key-value metadata attached to the
            Nomba order.
        access_token:
            Optional existing Nomba access token.  If not provided,
            a fresh token is obtained via ``NombaAuthService``.

        Returns
        -------
        NombaCheckoutInitResult
            A frozen dataclass with the checkout link, order
            reference, and local payment/sale IDs.

        Raises
        ------
        NombaAuthenticationError
            If Nomba authentication fails.
        NombaConnectionError
            If a network error or timeout occurs.
        NombaInvalidResponseError
            If Nomba returns a malformed response.
        NombaRequestError
            If Nomba returns an unexpected non-2xx status.
        rest_framework.exceptions.ValidationError
            If the payment cannot be created (e.g. duplicate SUCCESS
            payment for the sale).
        """
        from apps.payments.models import Payment

        # --- Step 1: Obtain access token ---
        if access_token is None:
            auth = NombaAuthService()
            token_result = auth.get_access_token()
            access_token = token_result.access_token

        # --- Step 2: Create Nomba checkout order ---
        checkout = NombaCheckoutService(
            access_token=access_token,
            account_id=settings.NOMBA_ACCOUNT_ID,
        )
        order_result = checkout.create_order(
            amount=str(sale.total),
            currency="NGN",
            callback_url=callback_url,
            customer_email=customer_email,
            metadata=metadata,
        )

        # --- Step 3: Record a PENDING Payment ---
        payment = PaymentService.create_payment(
            workspace=sale.workspace,
            sale=sale,
            amount=sale.total,
            currency="NGN",
            payment_method=Payment.PaymentMethod.TRANSFER,
            status=Payment.Status.PENDING,
            provider_reference=order_result.order_reference,
            notes=f"Nomba checkout: {order_result.checkout_link}",
        )

        return NombaCheckoutInitResult(
            checkout_link=order_result.checkout_link,
            order_reference=order_result.order_reference,
            payment_id=str(payment.pk),
            sale_id=str(sale.pk),
        )

    @staticmethod
    def verify_and_update_payment(
        *,
        payment,
        access_token: str | None = None,
    ) -> PaymentVerificationResult:
        """Verify a payment with Nomba and update local status.

        **Idempotent:** If the ``Payment`` is already ``SUCCESS``,
        the method skips the Nomba verification entirely and returns
        immediately with the current status. This prevents duplicate
        updates from repeated webhook calls.

        This method:

        1. Verifies the transaction status with Nomba via
           ``NombaTransactionService`` (unless already SUCCESS).
        2. If Nomba reports ``SUCCESS``, updates the ``Payment`` to
           ``SUCCESS`` via ``PaymentService`` and marks the ``Sale``
           as ``PAID``.
        3. If Nomba reports ``FAILED``, updates the ``Payment`` to
           ``FAILED`` via ``PaymentService``.

        **Only** ``PaymentService`` may change payment status. This
        method delegates all status transitions to
        ``PaymentService.update_payment_status()``.

        Parameters
        ----------
        payment:
            The ``Payment`` instance to verify and update. Must have
            a ``provider_reference`` (the Nomba order reference).
        access_token:
            Optional existing Nomba access token.  If not provided,
            a fresh token is obtained via ``NombaAuthService``.

        Returns
        -------
        PaymentVerificationResult
            A frozen dataclass with the old/new statuses.

        Raises
        ------
        ValueError
            If the payment has no ``provider_reference``.
        NombaAuthenticationError
            If Nomba authentication fails.
        NombaConnectionError
            If a network error or timeout occurs.
        NombaInvalidResponseError
            If Nomba returns a malformed response.
        NombaRequestError
            If Nomba returns an unexpected non-2xx status.
        rest_framework.exceptions.ValidationError
            If the payment status transition is not allowed.
        """
        from django.db import transaction as db_transaction

        from apps.payments.models import Payment
        from apps.sales.models import Sale

        order_ref = payment.provider_reference
        if not order_ref:
            raise ValueError(
                "Cannot verify payment without a provider_reference. "
                "Ensure the payment was created via initiate_checkout()."
            )

        # --- Idempotency: skip if already SUCCESS ---
        if payment.status == Payment.Status.SUCCESS:
            return PaymentVerificationResult(
                payment_id=str(payment.pk),
                sale_id=str(payment.sale_id),
                old_status=payment.status,
                new_status=payment.status,
                sale_payment_status=payment.sale.payment_status,
                nomba_status="SUCCESS",
            )

        # --- Step 1: Verify with Nomba ---
        if access_token is None:
            auth = NombaAuthService()
            token_result = auth.get_access_token()
            access_token = token_result.access_token

        txn_service = NombaTransactionService(
            access_token=access_token,
            account_id=settings.NOMBA_ACCOUNT_ID,
        )
        verify_result = txn_service.verify_transaction(
            order_reference=order_ref,
        )

        old_status = payment.status

        with db_transaction.atomic():
            # --- Step 2: Update Payment status via PaymentService (truth layer) ---
            if verify_result.is_successful:
                payment = PaymentService.update_payment_status(
                    payment=payment,
                    new_status=Payment.Status.SUCCESS,
                )
            elif (
                verify_result.nomba_status == "FAILED"
                and payment.status == Payment.Status.PENDING
            ):
                payment = PaymentService.update_payment_status(
                    payment=payment,
                    new_status=Payment.Status.FAILED,
                )

            # --- Step 3: Update Sale payment_status ---
            sale = payment.sale
            if payment.status == Payment.Status.SUCCESS:
                if sale.payment_status != Sale.PaymentStatus.PAID:
                    sale.payment_status = Sale.PaymentStatus.PAID
                    sale.save(update_fields=["payment_status", "updated_at"])

        return PaymentVerificationResult(
            payment_id=str(payment.pk),
            sale_id=str(payment.sale_id),
            old_status=old_status,
            new_status=payment.status,
            sale_payment_status=sale.payment_status,
            nomba_status=verify_result.nomba_status,
        )
