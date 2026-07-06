"""
Tests for Nomba verification views.

Covers:
- VerifyPaymentView (authenticated, payment not found, success, missing ref)
- Nomba webhook endpoint (valid payload, HMAC signature, idempotency,
  invalid JSON, missing order)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.payments.integrations.nomba.services import (
    PaymentVerificationResult,
)
from apps.payments.models import Payment, WebhookEvent
from apps.products.models import Product
from apps.inventory.models import Inventory
from apps.sales.models import Sale
from apps.workspaces.models import Workspace, WorkspaceMembership

NOMBA_SETTINGS = {
    "NOMBA_BASE_URL": "https://sandbox.nomba.com",
    "NOMBA_CLIENT_ID": "test_client_id",
    "NOMBA_CLIENT_SECRET": "test_client_secret",
    "NOMBA_ACCOUNT_ID": "test_account_id",
    "NOMBA_WEBHOOK_SECRET": "test-webhook-secret",
}


def _sign_payload(payload: dict, secret: str = "test-webhook-secret") -> str:
    """Create an HMAC-SHA256 signature for the given payload."""
    body = json.dumps(payload).encode("utf-8")
    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={expected}"


# ======================================================================
# VerifyPaymentView tests
# ======================================================================


@override_settings(**NOMBA_SETTINGS)
class VerifyPaymentViewTests(APITestCase):
    """Test the manual payment verification endpoint."""

    def setUp(self) -> None:
        """Create user, workspace, membership, and authenticate."""
        self.user = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            first_name="Jane",
            last_name="Doe",
        )
        self.workspace = Workspace.objects.create(
            owner=self.user,
            name="Test Store",
            slug="test-store",
        )
        WorkspaceMembership.objects.create(
            user=self.user,
            workspace=self.workspace,
            role=WorkspaceMembership.Role.OWNER,
        )

        self._authenticate(self.user)

        # Create a product and inventory
        self.product = Product.objects.create(
            workspace=self.workspace,
            name="Test Product",
            sku="TST-001",
            cost_price="5.00",
            selling_price="12.99",
        )
        Inventory.objects.create(product=self.product, quantity=100)

        # Create a sale
        self.sale = Sale.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            subtotal=Decimal("25.98"),
            total=Decimal("25.98"),
        )

        # Create a PENDING payment with provider_reference
        self.payment = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("25.98"),
            payment_method=Payment.PaymentMethod.TRANSFER,
            status=Payment.Status.PENDING,
            provider_reference="nomba-test-ref-001",
        )

        self.verify_url = reverse(
            "payments:payment-verify",
            args=[self.payment.pk],
        )
        self.verify_url_wrong_pk = reverse(
            "payments:payment-verify",
            args=[uuid.uuid4()],
        )

    def _authenticate(self, user: User) -> None:
        """Set JWT credentials."""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def test_unauthenticated_returns_401(self) -> None:
        """POST without auth returns 401."""
        self.client.credentials()
        response = self.client.post(self.verify_url)
        self.assertEqual(
            response.status_code, status.HTTP_401_UNAUTHORIZED,
        )

    # ------------------------------------------------------------------
    # Not found
    # ------------------------------------------------------------------

    def test_nonexistent_payment_returns_404(self) -> None:
        """POST with a non-existent payment UUID returns 404."""
        response = self.client.post(self.verify_url_wrong_pk)
        self.assertEqual(
            response.status_code, status.HTTP_404_NOT_FOUND,
        )

    # ------------------------------------------------------------------
    # Missing provider reference
    # ------------------------------------------------------------------

    def test_payment_without_provider_ref_returns_400(self) -> None:
        """POST for a payment without provider_reference returns 400."""
        cash_payment = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("10.00"),
            payment_method=Payment.PaymentMethod.CASH,
        )
        url = reverse(
            "payments:payment-verify",
            args=[cash_payment.pk],
        )
        response = self.client.post(url)
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST,
        )

    # ------------------------------------------------------------------
    # Successful verification
    # ------------------------------------------------------------------

    def test_successful_verification_returns_200(self) -> None:
        """A valid payment returns 200 with status details."""
        with patch(
            "apps.payments.integrations.nomba.views.NombaPaymentService.verify_and_update_payment"  # noqa: E501
        ) as mock_verify:
            mock_verify.return_value = PaymentVerificationResult(
                payment_id=str(self.payment.pk),
                sale_id=str(self.sale.pk),
                old_status="PENDING",
                new_status="SUCCESS",
                sale_payment_status="PAID",
                nomba_status="SUCCESS",
            )

            response = self.client.post(self.verify_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_id"], str(self.payment.pk))
        self.assertEqual(response.data["new_status"], "SUCCESS")
        self.assertEqual(response.data["sale_payment_status"], "PAID")
        self.assertEqual(response.data["nomba_status"], "SUCCESS")

    def test_verification_mirrors_nomba_status(self) -> None:
        """Response shows the actual Nomba status (e.g. PENDING)."""
        with patch(
            "apps.payments.integrations.nomba.views.NombaPaymentService.verify_and_update_payment"  # noqa: E501
        ) as mock_verify:
            mock_verify.return_value = PaymentVerificationResult(
                payment_id=str(self.payment.pk),
                sale_id=str(self.sale.pk),
                old_status="PENDING",
                new_status="PENDING",
                sale_payment_status="PENDING_PAYMENT",
                nomba_status="PENDING",
            )

            response = self.client.post(self.verify_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["nomba_status"], "PENDING")
        self.assertEqual(response.data["new_status"], "PENDING")


# ======================================================================
# Webhook tests
# ======================================================================


@override_settings(**NOMBA_SETTINGS)
class NombaWebhookTests(APITestCase):
    """Test the Nomba webhook endpoint at /api/webhooks/nomba/."""

    def setUp(self) -> None:
        self.webhook_url = reverse("nomba-webhook")

    def _post_webhook(
        self,
        payload: dict,
        signature: str | None = None,
    ) -> JsonResponse:
        """Helper to POST a webhook payload with optional HMAC signature."""
        body = json.dumps(payload)
        headers = {"content_type": "application/json"}
        if signature is not None:
            headers["HTTP_X_NOMBA_SIGNATURE"] = signature
        return self.client.post(
            self.webhook_url,
            data=body,
            **headers,
        )

    # ------------------------------------------------------------------
    # HMAC signature verification
    # ------------------------------------------------------------------

    def test_valid_signature_returns_200(self) -> None:
        """A properly signed webhook returns 200."""
        payload = {
            "eventId": "evt-001",
            "event": "checkout.completed",
            "data": {
                "orderReference": "order-ref-001",
                "status": "SUCCESS",
            },
        }
        signature = _sign_payload(payload)
        response = self._post_webhook(payload, signature=signature)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "received")

    def test_invalid_signature_returns_401(self) -> None:
        """An incorrectly signed webhook returns 401."""
        payload = {
            "eventId": "evt-002",
            "data": {"orderReference": "order-ref-002"},
        }
        response = self._post_webhook(payload, signature="sha256=badbadbad")
        self.assertEqual(
            response.status_code, status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(response.json()["status"], "invalid_signature")

    def test_missing_signature_still_allowed_when_no_secret(self) -> None:
        """Without NOMBA_WEBHOOK_SECRET, signature check is skipped."""
        with self.settings(NOMBA_WEBHOOK_SECRET=""):
            payload = {
                "eventId": "evt-003",
                "data": {"orderReference": "order-ref-003"},
            }
            response = self._post_webhook(payload)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def test_duplicate_event_id_is_skipped(self) -> None:
        """A duplicate eventId is acknowledged but not re-processed."""
        # First call
        payload = {
            "eventId": "evt-101",
            "event": "checkout.completed",
            "data": {"orderReference": "order-ref-101"},
        }
        signature = _sign_payload(payload)
        response1 = self._post_webhook(payload, signature=signature)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second call with same eventId
        response2 = self._post_webhook(payload, signature=signature)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.json()["status"], "already_received")

    def test_different_event_id_processes_normally(self) -> None:
        """Different eventIds are both processed."""
        payload1 = {
            "eventId": "evt-201",
            "data": {"orderReference": "order-ref-201"},
        }
        payload2 = {
            "eventId": "evt-202",
            "data": {"orderReference": "order-ref-202"},
        }
        sig1 = _sign_payload(payload1)
        sig2 = _sign_payload(payload2)

        r1 = self._post_webhook(payload1, signature=sig1)
        r2 = self._post_webhook(payload2, signature=sig2)

        self.assertEqual(r1.json()["status"], "received")
        self.assertEqual(r2.json()["status"], "received")

    # ------------------------------------------------------------------
    # Event tracking record
    # ------------------------------------------------------------------

    @patch("apps.payments.integrations.nomba.views.NombaPaymentService.verify_and_update_payment")  # noqa: E501
    def test_webhook_creates_event_record(
        self, mock_verify: object
    ) -> None:
        """A processed webhook creates a WebhookEvent record."""
        # Create a payment that the webhook can find
        from decimal import Decimal
        from apps.sales.models import Sale
        from apps.products.models import Product
        from apps.inventory.models import Inventory
        from apps.accounts.models import User
        from apps.workspaces.models import Workspace, WorkspaceMembership

        user = User.objects.create_user(
            email="webhook@example.com", password="testpass123",
        )
        workspace = Workspace.objects.create(
            owner=user, name="Webhook Store", slug="webhook-store",
        )
        WorkspaceMembership.objects.create(
            user=user, workspace=workspace, role=WorkspaceMembership.Role.OWNER,
        )
        product = Product.objects.create(
            workspace=workspace,
            name="Webhook Product", sku="WHK-001",
            cost_price="5.00", selling_price="20.00",
        )
        Inventory.objects.create(product=product, quantity=10)
        sale = Sale.objects.create(
            workspace=workspace, created_by=user,
            subtotal=Decimal("20.00"), total=Decimal("20.00"),
        )
        Payment.objects.create(
            workspace=workspace, sale=sale,
            amount=Decimal("20.00"),
            payment_method=Payment.PaymentMethod.TRANSFER,
            provider_reference="order-ref-301",
        )

        payload = {
            "eventId": "evt-301",
            "event": "checkout.completed",
            "data": {"orderReference": "order-ref-301"},
        }
        signature = _sign_payload(payload)
        self._post_webhook(payload, signature=signature)

        event = WebhookEvent.objects.filter(event_id="evt-301").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.provider, "nomba")
        self.assertEqual(event.event_type, "checkout.completed")
        self.assertEqual(event.status, "processed")

    # ------------------------------------------------------------------
    # Invalid JSON
    # ------------------------------------------------------------------

    def test_invalid_json_returns_400(self) -> None:
        """Malformed JSON body returns 400."""
        response = self.client.post(
            self.webhook_url,
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(response.json()["status"], "invalid_json")

    # ------------------------------------------------------------------
    # Missing order reference
    # ------------------------------------------------------------------

    def test_missing_order_reference_still_returns_200(self) -> None:
        """A payload without orderReference still acknowledges."""
        payload = {"event": "unknown", "data": {}}
        signature = _sign_payload(payload)
        response = self._post_webhook(payload, signature=signature)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "received")

    # ------------------------------------------------------------------
    # Method restriction
    # ------------------------------------------------------------------

    def test_get_method_returns_405(self) -> None:
        """GET requests to the webhook are rejected."""
        response = self.client.get(self.webhook_url)
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED,
        )
