"""
API views for Nomba payment verification.

Provides two ways to verify a Nomba payment:

1. **Manual verification** — an authenticated merchant endpoint that
   verifies a payment and updates local status atomically.
2. **Webhook** — an unauthenticated endpoint that Nomba calls to
   notify MerchantHub of payment status changes, with HMAC signature
   verification and idempotent event handling.

Truth layer
-----------
**Only ``PaymentService`` updates money state.** ``NombaCheckoutService``
creates checkout orders but never sets ``SUCCESS``. Both the manual
verification endpoint and the webhook delegate status transitions to
``PaymentService.update_payment_status()``, which enforces valid
transitions (PENDING → SUCCESS/FAILED, FAILED → SUCCESS, SUCCESS → REFUNDED).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.payments.integrations.nomba import (
    NombaPaymentService,
)
from apps.payments.models import Payment, WebhookEvent

logger = logging.getLogger(__name__)


# ======================================================================
# Manual verification endpoint
# ======================================================================


class VerifyPaymentView(generics.GenericAPIView):
    """Verify a payment transaction with Nomba and update local status.

    **POST** ``/payments/<uuid>/verify/`` — Checks the transaction
    status with Nomba for the given payment. If Nomba reports
    ``SUCCESS``, the ``Payment`` is updated to ``SUCCESS`` and the
    associated ``Sale`` is marked as ``PAID``.

    Returns the old and new status of both the payment and the sale.

    Usage by the frontend::

        POST /api/v1/payments/<payment-uuid>/verify/
        Authorization: Bearer <jwt>

        Response 200:
        {
            "payment_id": "...",
            "sale_id": "...",
            "old_status": "PENDING",
            "new_status": "SUCCESS",
            "sale_payment_status": "PAID",
            "nomba_status": "SUCCESS"
        }
    """

    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["post"]

    def post(self, request: HttpRequest, pk: str) -> Response:
        """Verify the payment identified by ``pk``."""
        from apps.workspaces.utils import get_active_workspace

        workspace = get_active_workspace(request)

        try:
            payment = Payment.objects.get(
                pk=pk,
                workspace=workspace,
            )
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not payment.provider_reference:
            return Response(
                {
                    "error": (
                        "This payment has no provider reference and "
                        "cannot be verified. It may be a cash payment."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = NombaPaymentService.verify_and_update_payment(
                payment=payment,
            )
        except Exception:
            logger.exception(
                "Failed to verify payment %s with Nomba", pk
            )
            return Response(
                {"error": "Verification with Nomba failed. Try again later."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "payment_id": result.payment_id,
                "sale_id": result.sale_id,
                "old_status": result.old_status,
                "new_status": result.new_status,
                "sale_payment_status": result.sale_payment_status,
                "nomba_status": result.nomba_status,
            },
            status=status.HTTP_200_OK,
        )


# ======================================================================
# Webhook signature helpers
# ======================================================================


def _verify_nomba_signature(
    payload_body: bytes,
    signature_header: str,
) -> bool:
    """Verify an HMAC-SHA256 signature from Nomba.

    Nomba signs the request body using HMAC-SHA256 and includes the
    digest in the ``X-Nomba-Signature`` header.

    Parameters
    ----------
    payload_body:
        The raw request body bytes.
    signature_header:
        The value of the ``X-Nomba-Signature`` header.

    Returns
    -------
    bool
        ``True`` if the signature is valid, ``False`` otherwise.
    """
    secret = settings.NOMBA_WEBHOOK_SECRET
    if not secret:
        logger.warning(
            "NOMBA_WEBHOOK_SECRET is not configured — "
            "webhook signature verification is disabled. "
            "Set NOMBA_WEBHOOK_SECRET in your Django settings "
            "for production use."
        )
        return True

    expected = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature_header)


def _extract_event_id(payload: dict) -> str:
    """Extract a unique event identifier from the webhook payload.

    Uses the ``eventId`` field if present, otherwise falls back to
    a hash of the payload to ensure idempotency even without an
    explicit event ID.
    """
    event_id = payload.get("eventId") or payload.get("id")
    if event_id:
        return str(event_id)

    # Fallback: hash the entire payload for idempotency
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


# ======================================================================
# Webhook endpoint (called by Nomba)
# ======================================================================


@csrf_exempt
@require_POST
def nomba_webhook(request: HttpRequest) -> JsonResponse:
    """Handle incoming Nomba webhook notifications.

    Nomba sends a ``POST`` request to this endpoint when the status
    of a checkout transaction changes. The endpoint:

    1. Verifies the HMAC-SHA256 signature (if configured).
    2. Checks for idempotency — duplicate ``eventId`` values are
       silently acknowledged but not re-processed.
    3. Extracts the ``orderReference`` and looks up the matching
       ``Payment``.
    4. Calls ``NombaPaymentService.verify_and_update_payment()``
       which goes through ``PaymentService`` (the single truth
       layer for money state).

    Returns ``200 OK`` with ``{"status": "received"}``.
    """
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning("Nomba webhook received invalid JSON")
        return JsonResponse(
            {"status": "invalid_json"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --- Step 1: Verify HMAC signature ---
    signature = request.headers.get("X-Nomba-Signature", "")
    if not _verify_nomba_signature(request.body, signature):
        logger.warning(
            "Nomba webhook received invalid signature: %s", signature,
        )
        return JsonResponse(
            {"status": "invalid_signature"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # --- Step 2: Idempotency check (atomic get_or_create) ---
    event_id = _extract_event_id(payload)
    event_type = payload.get("event", "unknown")

    event, created = WebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            "provider": "nomba",
            "event_type": event_type,
            "status": "processing",
            "payload": payload,
        },
    )
    if not created:
        logger.info(
            "Nomba webhook event %s already processed — skipped", event_id,
        )
        return JsonResponse({"status": "already_received"})

    # --- Step 3: Process the webhook ---
    data = payload.get("data", {})
    order_ref = data.get("orderReference")

    if order_ref:
        try:
            payment = Payment.objects.get(
                provider_reference=order_ref,
            )

            NombaPaymentService.verify_and_update_payment(
                payment=payment,
            )

            event.status = "processed"
            event.save(update_fields=["status"])

            logger.info(
                "Nomba webhook processed: event=%s order=%s",
                event_type, order_ref,
            )

        except Payment.DoesNotExist:
            logger.warning(
                "Nomba webhook: no payment found for order %s", order_ref,
            )
            event.status = "skipped_no_payment"
            event.save(update_fields=["status"])
        except Exception:
            logger.exception(
                "Nomba webhook: failed to process payment for %s",
                order_ref,
            )
            event.status = "failed"
            event.save(update_fields=["status"])
    else:
        event.status = "skipped_no_order_ref"
        event.save(update_fields=["status"])
        logger.info(
            "Nomba webhook received without orderReference: event=%s",
            event_type,
        )

    return JsonResponse({"status": "received"})
