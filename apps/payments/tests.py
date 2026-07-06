"""
Comprehensive tests for the Payment model, serializer, service, and API.

Covers model creation, serialization, service-layer business rules,
full CRUD API, workspace isolation, authentication, search,
ordering, pagination, validations, and method restrictions.
"""

import uuid

from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.payments.models import Payment
from apps.payments.services import PaymentService
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem
from apps.inventory.models import Inventory
from apps.workspaces.models import Workspace, WorkspaceMembership


# ======================================================================
# Helpers
# ======================================================================


def _create_sale_for_workspace(
    workspace: Workspace,
    product: Product,
    quantity: int = 2,
) -> Sale:
    """Create a sale with a single line item for testing."""
    from apps.sales.services import SalesService

    # Ensure inventory exists
    inv, _ = Inventory.objects.get_or_create(
        product=product,
        defaults={"quantity": 999},
    )

    # Get a user from workspace
    user = workspace.owner

    return SalesService.create_sale(
        workspace=workspace,
        created_by=user,
        items=[
            {"product": product, "quantity": quantity},
        ],
    )


# ======================================================================
# Model tests
# ======================================================================


class PaymentModelTests(APITestCase):
    """Verify Payment model creation, fields, choices, and constraints."""

    def setUp(self) -> None:
        """Create a user, workspace, product, inventory, and sale."""
        self.user = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            first_name="Jane",
            last_name="Doe",
        )
        self.workspace = Workspace.objects.create(
            owner=self.user, name="Test Store", slug="test-store",
        )
        WorkspaceMembership.objects.create(
            user=self.user,
            workspace=self.workspace,
            role=WorkspaceMembership.Role.OWNER,
        )
        self.product = Product.objects.create(
            workspace=self.workspace,
            name="Test Product",
            sku="TST-001",
            cost_price="5.00",
            selling_price="12.99",
        )
        Inventory.objects.create(product=self.product, quantity=100)
        self.sale = _create_sale_for_workspace(self.workspace, self.product)

    def test_create_payment(self) -> None:
        """A Payment can be created with valid fields."""
        payment = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.SUCCESS,
            provider_reference="nomba_ref_001",
            external_reference="REC-001",
            notes="Payment via cash",
        )
        self.assertIsNotNone(payment.pk)
        self.assertEqual(payment.amount, Decimal("12.99"))
        self.assertEqual(payment.currency, "NGN")
        self.assertEqual(payment.payment_method, "CASH")
        self.assertEqual(payment.status, "SUCCESS")
        self.assertEqual(payment.provider_reference, "nomba_ref_001")
        self.assertEqual(payment.external_reference, "REC-001")
        self.assertEqual(payment.notes, "Payment via cash")

    def test_payment_method_choices(self) -> None:
        """All valid payment methods are accepted."""
        for method in ["CASH", "TRANSFER", "CARD", "POS", "OTHER"]:
            payment = Payment.objects.create(
                workspace=self.workspace,
                sale=self.sale,
                amount=Decimal("10.00"),
                payment_method=method,
            )
            self.assertEqual(payment.payment_method, method)

    def test_status_choices(self) -> None:
        """All valid status values are accepted."""
        for st in ["PENDING", "SUCCESS", "FAILED", "REFUNDED"]:
            payment = Payment.objects.create(
                workspace=self.workspace,
                sale=self.sale,
                amount=Decimal("10.00"),
                payment_method="CASH",
                status=st,
            )
            self.assertEqual(payment.status, st)

    def test_default_currency(self) -> None:
        """Currency defaults to NGN."""
        payment = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("10.00"),
            payment_method="CASH",
        )
        self.assertEqual(payment.currency, "NGN")

    def test_default_status(self) -> None:
        """Status defaults to PENDING."""
        payment = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("10.00"),
            payment_method="CASH",
        )
        self.assertEqual(payment.status, "PENDING")

    def test_customer_nullable(self) -> None:
        """Customer can be null."""
        payment = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("10.00"),
            payment_method="CASH",
        )
        self.assertIsNone(payment.customer)

    def test_provider_reference_nullable(self) -> None:
        """provider_reference can be null/blank."""
        payment = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("10.00"),
            payment_method="CASH",
        )
        self.assertIsNone(payment.provider_reference)

    def test_external_reference_nullable(self) -> None:
        """external_reference can be null/blank."""
        payment = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("10.00"),
            payment_method="CASH",
        )
        self.assertIsNone(payment.external_reference)

    def test_amount_positive_constraint(self) -> None:
        """A payment with non-positive amount is rejected."""
        with self.assertRaises(Exception):
            Payment.objects.create(
                workspace=self.workspace,
                sale=self.sale,
                amount=Decimal("0.00"),
                payment_method="CASH",
            )

    def test_str_representation(self) -> None:
        """__str__ shows amount, currency, and status."""
        payment = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("15.50"),
            currency="NGN",
            payment_method="TRANSFER",
            status="SUCCESS",
        )
        result = str(payment)
        self.assertIn("15.50", result)
        self.assertIn("NGN", result)
        self.assertIn("SUCCESS", result)

    def test_ordering_newest_first(self) -> None:
        """Payments are ordered by created_at descending."""
        p1 = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("10.00"),
            payment_method="CASH",
        )
        p2 = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("20.00"),
            payment_method="TRANSFER",
        )
        qs = Payment.objects.all()
        self.assertEqual(qs[0], p2)
        self.assertEqual(qs[1], p1)

    def test_cascade_on_workspace_delete(self) -> None:
        """Deleting a workspace cascades to its payments."""
        Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("10.00"),
            payment_method="CASH",
        )
        # Cascade requires deleting protected objects first.
        # Payment.sale uses PROTECT, SaleItem.product uses PROTECT.
        Payment.objects.filter(workspace=self.workspace).delete()
        self.sale.items.all().delete()
        self.sale.delete()
        Inventory.objects.filter(product__workspace=self.workspace).delete()
        Product.objects.filter(workspace=self.workspace).delete()
        self.workspace.delete()
        self.assertEqual(Payment.objects.count(), 0)

    def test_protect_on_sale_delete(self) -> None:
        """Deleting a sale with payments is protected."""
        Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("10.00"),
            payment_method="CASH",
        )
        with self.assertRaises(Exception):
            self.sale.delete()

    def test_set_null_on_customer_delete(self) -> None:
        """Deleting a customer sets payment's customer to null."""
        customer = Customer.objects.create(
            workspace=self.workspace,
            first_name="John",
            phone_number="+1234567890",
        )
        payment = Payment.objects.create(
            workspace=self.workspace,
            sale=self.sale,
            customer=customer,
            amount=Decimal("10.00"),
            payment_method="CASH",
        )
        customer.delete()
        payment.refresh_from_db()
        self.assertIsNone(payment.customer)


# ======================================================================
# Service tests
# ======================================================================


class PaymentServiceTests(APITestCase):
    """Verify PaymentService business rules — creation, status
    transitions, single-success enforcement, and validation."""

    def setUp(self) -> None:
        """Create users, workspaces, products, sales, and customers."""
        self.user = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            first_name="Jane",
            last_name="Doe",
        )
        self.workspace = Workspace.objects.create(
            owner=self.user, name="Test Store", slug="test-store",
        )
        WorkspaceMembership.objects.create(
            user=self.user,
            workspace=self.workspace,
            role=WorkspaceMembership.Role.OWNER,
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            first_name="Other",
            last_name="User",
        )
        self.other_workspace = Workspace.objects.create(
            owner=self.other_user, name="Other Store", slug="other-store",
        )
        WorkspaceMembership.objects.create(
            user=self.other_user,
            workspace=self.other_workspace,
            role=WorkspaceMembership.Role.OWNER,
        )

        self.product = Product.objects.create(
            workspace=self.workspace,
            name="Test Product", sku="TST-001",
            cost_price="5.00", selling_price="12.99",
        )
        Inventory.objects.create(product=self.product, quantity=100)

        self.other_product = Product.objects.create(
            workspace=self.other_workspace,
            name="Other Product", sku="OTH-001",
            cost_price="5.00", selling_price="24.99",
        )
        Inventory.objects.create(product=self.other_product, quantity=100)

        self.sale = _create_sale_for_workspace(self.workspace, self.product)
        self.other_sale = _create_sale_for_workspace(
            self.other_workspace, self.other_product,
        )

        self.customer = Customer.objects.create(
            workspace=self.workspace,
            first_name="John",
            phone_number="+1234567890",
        )
        self.other_customer = Customer.objects.create(
            workspace=self.other_workspace,
            first_name="Bob",
            phone_number="+9999999999",
        )

    # ------------------------------------------------------------------
    # create_payment
    # ------------------------------------------------------------------

    def test_create_payment_success(self) -> None:
        """A valid payment is created successfully."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
            customer=self.customer,
            provider_reference="ref_001",
            external_reference="EXT-001",
            notes="Test payment",
        )
        self.assertIsNotNone(payment.pk)
        self.assertEqual(payment.amount, Decimal("12.99"))
        self.assertEqual(payment.payment_method, "CASH")
        self.assertEqual(payment.status, "PENDING")
        self.assertEqual(payment.customer, self.customer)

    def test_create_payment_without_customer(self) -> None:
        """A payment can be created without a customer."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
        )
        self.assertIsNotNone(payment.pk)
        self.assertIsNone(payment.customer)

    def test_create_payment_without_references(self) -> None:
        """References are optional."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
        )
        self.assertIsNone(payment.provider_reference)
        self.assertIsNone(payment.external_reference)

    def test_create_payment_wrong_workspace_sale_raises_error(self) -> None:
        """A sale from another workspace raises ValidationError."""
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                workspace=self.workspace,
                sale=self.other_sale,
                amount=Decimal("12.99"),
                payment_method="CASH",
            )

    def test_create_payment_wrong_workspace_customer_raises_error(self) -> None:
        """A customer from another workspace raises ValidationError."""
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                workspace=self.workspace,
                sale=self.sale,
                amount=Decimal("12.99"),
                payment_method="CASH",
                customer=self.other_customer,
            )

    def test_create_payment_zero_amount_raises_error(self) -> None:
        """A zero amount raises ValidationError."""
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                workspace=self.workspace,
                sale=self.sale,
                amount=Decimal("0.00"),
                payment_method="CASH",
            )

    def test_create_payment_negative_amount_raises_error(self) -> None:
        """A negative amount raises ValidationError."""
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                workspace=self.workspace,
                sale=self.sale,
                amount=Decimal("-10.00"),
                payment_method="CASH",
            )

    def test_create_payment_amount_is_none_raises_error(self) -> None:
        """None amount raises ValidationError."""
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                workspace=self.workspace,
                sale=self.sale,
                amount=None,
                payment_method="CASH",
            )

    def test_create_successful_payment_allowed_once(self) -> None:
        """Creating a SUCCESS payment is allowed once."""
        PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
            status="SUCCESS",
        )
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                workspace=self.workspace,
                sale=self.sale,
                amount=Decimal("12.99"),
                payment_method="CASH",
                status="SUCCESS",
            )

    def test_create_multiple_pending_allowed(self) -> None:
        """Multiple PENDING payments for the same sale are allowed."""
        PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("10.00"),
            payment_method="CASH",
        )
        PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("2.99"),
            payment_method="TRANSFER",
        )
        self.assertEqual(
            Payment.objects.filter(sale=self.sale).count(), 2,
        )

    def test_payment_created_with_status_success(self) -> None:
        """A payment created with status SUCCESS is saved correctly."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
            status="SUCCESS",
        )
        self.assertEqual(payment.status, "SUCCESS")

    # ------------------------------------------------------------------
    # update_payment_status
    # ------------------------------------------------------------------

    def test_pending_to_success(self) -> None:
        """PENDING → SUCCESS is a valid transition."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
        )
        updated = PaymentService.update_payment_status(
            payment=payment,
            new_status="SUCCESS",
        )
        self.assertEqual(updated.status, "SUCCESS")

    def test_pending_to_failed(self) -> None:
        """PENDING → FAILED is a valid transition."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
        )
        updated = PaymentService.update_payment_status(
            payment=payment,
            new_status="FAILED",
        )
        self.assertEqual(updated.status, "FAILED")

    def test_success_to_refunded(self) -> None:
        """SUCCESS → REFUNDED is a valid transition."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
            status="SUCCESS",
        )
        updated = PaymentService.update_payment_status(
            payment=payment,
            new_status="REFUNDED",
        )
        self.assertEqual(updated.status, "REFUNDED")

    def test_pending_to_refunded_raises_error(self) -> None:
        """PENDING → REFUNDED is invalid."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
        )
        with self.assertRaises(ValidationError):
            PaymentService.update_payment_status(
                payment=payment,
                new_status="REFUNDED",
            )

    def test_success_to_failed_raises_error(self) -> None:
        """SUCCESS → FAILED is invalid."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
            status="SUCCESS",
        )
        with self.assertRaises(ValidationError):
            PaymentService.update_payment_status(
                payment=payment,
                new_status="FAILED",
            )

    def test_failed_to_success(self) -> None:
        """FAILED → SUCCESS is a valid transition."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
        )
        PaymentService.update_payment_status(
            payment=payment, new_status="FAILED",
        )
        # Allow retrying a failed payment
        updated = PaymentService.update_payment_status(
            payment=payment, new_status="SUCCESS",
        )
        self.assertEqual(updated.status, "SUCCESS")

    def test_single_success_enforced_on_status_update(self) -> None:
        """Updating a payment to SUCCESS fails if another SUCCESS exists."""
        PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
            status="SUCCESS",
        )
        other = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("5.00"),
            payment_method="CASH",
        )
        with self.assertRaises(ValidationError):
            PaymentService.update_payment_status(
                payment=other,
                new_status="SUCCESS",
            )

    def test_successful_payment_can_refund_and_recharge(self) -> None:
        """After refunding a SUCCESS payment, a new SUCCESS is allowed."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
            status="SUCCESS",
        )
        PaymentService.refund_payment(payment=payment)

        # A new payment for the same sale can be SUCCESS now
        payment2 = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
            status="SUCCESS",
        )
        self.assertEqual(payment2.status, "SUCCESS")

    # ------------------------------------------------------------------
    # refund_payment
    # ------------------------------------------------------------------

    def test_refund_payment_success(self) -> None:
        """A successful payment can be refunded."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
            status="SUCCESS",
        )
        refunded = PaymentService.refund_payment(payment=payment)
        self.assertEqual(refunded.status, "REFUNDED")

    def test_refund_pending_payment_raises_error(self) -> None:
        """A pending payment cannot be refunded."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
        )
        with self.assertRaises(ValidationError):
            PaymentService.refund_payment(payment=payment)

    def test_refund_failed_payment_raises_error(self) -> None:
        """A failed payment cannot be refunded."""
        payment = PaymentService.create_payment(
            workspace=self.workspace,
            sale=self.sale,
            amount=Decimal("12.99"),
            payment_method="CASH",
        )
        PaymentService.update_payment_status(
            payment=payment, new_status="FAILED",
        )
        with self.assertRaises(ValidationError):
            PaymentService.refund_payment(payment=payment)


# ======================================================================
# Serializer tests
# ======================================================================


class PaymentSerializerTests(APITestCase):
    """Verify PaymentSerializer output and validation."""

    def setUp(self) -> None:
        """Create resources and authenticate."""
        self.user = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            first_name="Jane", last_name="Doe",
        )
        self.workspace = Workspace.objects.create(
            owner=self.user, name="Test Store", slug="test-store",
        )
        WorkspaceMembership.objects.create(
            user=self.user,
            workspace=self.workspace,
            role=WorkspaceMembership.Role.OWNER,
        )
        self.product = Product.objects.create(
            workspace=self.workspace,
            name="Test Product", sku="TST-001",
            cost_price="5.00", selling_price="12.99",
        )
        Inventory.objects.create(product=self.product, quantity=100)
        self.sale = _create_sale_for_workspace(self.workspace, self.product)

        self._authenticate(self.user)
        self.list_url = reverse("payments:payment-list")
        self.valid_payload = {
            "sale": str(self.sale.pk),
            "amount": "12.99",
            "payment_method": "CASH",
        }

    def _authenticate(self, user: User) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )

    def test_serialized_output_contains_expected_fields(self) -> None:
        """The serialized output includes all specified fields."""
        response = self.client.post(
            self.list_url, self.valid_payload, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertIn("id", data)
        self.assertIn("sale", data)
        self.assertIn("customer", data)
        self.assertIn("amount", data)
        self.assertIn("currency", data)
        self.assertIn("payment_method", data)
        self.assertIn("status", data)
        self.assertIn("provider_reference", data)
        self.assertIn("external_reference", data)
        self.assertIn("notes", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
        # Workspace must never be exposed
        self.assertNotIn("workspace", data)

    def test_serialized_values_match_input(self) -> None:
        """The serialized values match the input data."""
        response = self.client.post(
            self.list_url, self.valid_payload, format="json",
        )
        data = response.data
        self.assertEqual(str(data["sale"]), str(self.sale.pk))
        self.assertEqual(Decimal(data["amount"]), Decimal("12.99"))
        self.assertEqual(data["payment_method"], "CASH")
        self.assertEqual(data["currency"], "NGN")
        self.assertEqual(data["status"], "PENDING")

    def test_serialized_customer_null(self) -> None:
        """Customer field is None when not provided."""
        response = self.client.post(
            self.list_url, self.valid_payload, format="json",
        )
        self.assertIsNone(response.data["customer"])

    def test_serializer_sale_from_other_workspace_raises_error(self) -> None:
        """A sale from another workspace is rejected by the serializer."""
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123",
        )
        other_workspace = Workspace.objects.create(
            owner=other_user, name="Other", slug="other",
        )
        WorkspaceMembership.objects.create(
            user=other_user, workspace=other_workspace,
            role=WorkspaceMembership.Role.OWNER,
        )
        other_product = Product.objects.create(
            workspace=other_workspace,
            name="Other", sku="OTH-001",
            cost_price="5.00", selling_price="24.99",
        )
        Inventory.objects.create(product=other_product, quantity=100)
        other_sale = _create_sale_for_workspace(other_workspace, other_product)

        payload = {
            "sale": str(other_sale.pk),
            "amount": "12.99",
            "payment_method": "CASH",
        }
        response = self.client.post(
            self.list_url, payload, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ======================================================================
# API / View tests
# ======================================================================


class PaymentAPITests(APITestCase):
    """Test all Payment API endpoints — CRUD, auth, workspace
    isolation, search, ordering, pagination, and validation."""

    def setUp(self) -> None:
        """Create users, workspaces, products, sales, customers,
        and authenticate the primary user."""
        # ------------------------------------------------------------------
        # Primary user & workspace
        # ------------------------------------------------------------------
        self.user = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            first_name="Jane", last_name="Doe",
        )
        self.workspace = Workspace.objects.create(
            owner=self.user, name="Test Store", slug="test-store",
        )
        WorkspaceMembership.objects.create(
            user=self.user,
            workspace=self.workspace,
            role=WorkspaceMembership.Role.OWNER,
        )

        # ------------------------------------------------------------------
        # Second user & workspace (isolation tests)
        # ------------------------------------------------------------------
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            first_name="Other", last_name="User",
        )
        self.other_workspace = Workspace.objects.create(
            owner=self.other_user, name="Other Store", slug="other-store",
        )
        WorkspaceMembership.objects.create(
            user=self.other_user,
            workspace=self.other_workspace,
            role=WorkspaceMembership.Role.OWNER,
        )

        # ------------------------------------------------------------------
        # Products & inventory
        # ------------------------------------------------------------------
        self.product = Product.objects.create(
            workspace=self.workspace,
            name="Test Product", sku="TST-001",
            cost_price="5.00", selling_price="12.99",
        )
        Inventory.objects.create(product=self.product, quantity=100)

        self.other_product = Product.objects.create(
            workspace=self.other_workspace,
            name="Other Product", sku="OTH-001",
            cost_price="5.00", selling_price="24.99",
        )
        Inventory.objects.create(product=self.other_product, quantity=100)

        # ------------------------------------------------------------------
        # Sales
        # ------------------------------------------------------------------
        self.sale = _create_sale_for_workspace(self.workspace, self.product)
        self.other_sale = _create_sale_for_workspace(
            self.other_workspace, self.other_product,
        )

        # ------------------------------------------------------------------
        # Customers
        # ------------------------------------------------------------------
        self.customer = Customer.objects.create(
            workspace=self.workspace,
            first_name="John", phone_number="+1234567890",
        )
        self.other_customer = Customer.objects.create(
            workspace=self.other_workspace,
            first_name="Bob", phone_number="+9999999999",
        )

        # ------------------------------------------------------------------
        # Authentication & URLs
        # ------------------------------------------------------------------
        self._authenticate(self.user)
        self.list_url = reverse("payments:payment-list")
        self.valid_payload = {
            "sale": str(self.sale.pk),
            "amount": "12.99",
            "payment_method": "CASH",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _authenticate(self, user: User) -> None:
        """Set JWT authentication credentials on the test client."""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )

    def _create_payment(self, **overrides) -> dict:
        """Post a valid payment and return response data."""
        payload = {**self.valid_payload, **overrides}
        response = self.client.post(self.list_url, payload, format="json")
        return response.data

    # ==================================================================
    # AUTHENTICATION
    # ==================================================================

    def test_unauthenticated_create_returns_401(self) -> None:
        """POST /payments/ without auth returns 401."""
        self.client.credentials()
        response = self.client.post(
            self.list_url, self.valid_payload, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_list_returns_401(self) -> None:
        """GET /payments/ without auth returns 401."""
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_retrieve_returns_401(self) -> None:
        """GET /payments/<uuid>/ without auth returns 401."""
        data = self._create_payment()
        self.client.credentials()
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_update_returns_401(self) -> None:
        """PATCH /payments/<uuid>/ without auth returns 401."""
        data = self._create_payment()
        self.client.credentials()
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.patch(
            detail_url, {"status": "SUCCESS"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ==================================================================
    # CREATE
    # ==================================================================

    def test_create_payment_returns_201(self) -> None:
        """A valid payload returns HTTP 201."""
        response = self.client.post(
            self.list_url, self.valid_payload, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_payment_sets_correct_workspace(self) -> None:
        """The payment is scoped to the authenticated user's workspace."""
        self.client.post(self.list_url, self.valid_payload, format="json")
        payment = Payment.objects.get(sale=self.sale)
        self.assertEqual(payment.workspace, self.workspace)

    def test_create_payment_with_customer(self) -> None:
        """A customer can be attached to the payment."""
        payload = {
            **self.valid_payload,
            "customer": str(self.customer.pk),
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # DRF returns the FK value as a string via COERCE_DECIMAL_TO_STRING
        self.assertEqual(str(response.data["customer"]), str(self.customer.pk))

    def test_create_payment_zero_amount_returns_400(self) -> None:
        """Zero amount returns 400."""
        payload = {**self.valid_payload, "amount": "0.00"}
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_negative_amount_returns_400(self) -> None:
        """Negative amount returns 400."""
        payload = {**self.valid_payload, "amount": "-5.00"}
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_missing_amount_returns_400(self) -> None:
        """Missing amount returns 400."""
        payload = {
            "sale": str(self.sale.pk),
            "payment_method": "CASH",
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_missing_sale_returns_400(self) -> None:
        """Missing sale returns 400."""
        payload = {
            "amount": "12.99",
            "payment_method": "CASH",
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_missing_payment_method_returns_400(self) -> None:
        """Missing payment_method returns 400."""
        payload = {
            "sale": str(self.sale.pk),
            "amount": "12.99",
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_sale_from_other_workspace_returns_400(self) -> None:
        """A sale from another workspace returns 400."""
        payload = {
            "sale": str(self.other_sale.pk),
            "amount": "12.99",
            "payment_method": "CASH",
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_customer_from_other_workspace_returns_400(self) -> None:
        """A customer from another workspace returns 400."""
        payload = {
            **self.valid_payload,
            "customer": str(self.other_customer.pk),
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_nonexistent_sale_returns_400(self) -> None:
        """A non-existent sale UUID returns 400."""
        payload = {
            "sale": str(uuid.uuid4()),
            "amount": "12.99",
            "payment_method": "CASH",
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_with_provider_reference(self) -> None:
        """Provider reference is saved correctly."""
        data = self._create_payment(provider_reference="nomba_ref_001")
        self.assertEqual(data["provider_reference"], "nomba_ref_001")

    def test_create_payment_with_external_reference(self) -> None:
        """External reference is saved correctly."""
        data = self._create_payment(external_reference="REC-001")
        self.assertEqual(data["external_reference"], "REC-001")

    def test_create_payment_with_notes(self) -> None:
        """Notes are saved correctly."""
        data = self._create_payment(notes="Test note")
        self.assertEqual(data["notes"], "Test note")

    def test_create_payment_custom_currency(self) -> None:
        """Custom currency code is saved."""
        data = self._create_payment(currency="USD")
        self.assertEqual(data["currency"], "USD")

    def test_create_payment_success_status(self) -> None:
        """Creating a payment with SUCCESS status is accepted."""
        data = self._create_payment(status="SUCCESS")
        self.assertEqual(data["status"], "SUCCESS")

    def test_create_duplicate_success_payment_returns_400(self) -> None:
        """Creating a second SUCCESS payment for the same sale returns 400."""
        self._create_payment(status="SUCCESS")
        response = self.client.post(
            self.list_url,
            {**self.valid_payload, "status": "SUCCESS"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ==================================================================
    # LIST
    # ==================================================================

    def test_list_payments_returns_200(self) -> None:
        """GET /payments/ returns 200."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_payments_is_paginated(self) -> None:
        """The list response uses pagination."""
        response = self.client.get(self.list_url)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    def test_list_payments_returns_only_own_workspace(self) -> None:
        """Only payments from the user's workspace are returned."""
        self._create_payment()
        self._authenticate(self.other_user)
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_payments_newest_first(self) -> None:
        """Payments are ordered newest first."""
        data_a = self._create_payment(amount="10.00")
        data_b = self._create_payment(amount="20.00")
        response = self.client.get(self.list_url)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], data_b["id"])
        self.assertEqual(results[1]["id"], data_a["id"])

    def test_list_payments_multiple_workspaces_isolated(self) -> None:
        """Each workspace sees only its own payments."""
        self._create_payment()
        self._authenticate(self.other_user)
        other_payload = {
            "sale": str(self.other_sale.pk),
            "amount": "24.99",
            "payment_method": "TRANSFER",
        }
        self.client.post(self.list_url, other_payload, format="json")
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 1)

    # ==================================================================
    # SEARCH
    # ==================================================================

    def test_search_by_provider_reference(self) -> None:
        """?search= filters by provider_reference."""
        self._create_payment(provider_reference="nomba_ref_001")
        self._create_payment(
            provider_reference="nomba_ref_002",
            amount="24.99",
        )
        response = self.client.get(
            self.list_url, {"search": "nomba_ref_001"},
        )
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["provider_reference"], "nomba_ref_001",
        )

    def test_search_by_external_reference(self) -> None:
        """?search= filters by external_reference."""
        self._create_payment(external_reference="REC-001")
        self._create_payment(
            external_reference="REC-002", amount="24.99",
        )
        response = self.client.get(
            self.list_url, {"search": "REC-002"},
        )
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["external_reference"], "REC-002")

    def test_search_no_match_returns_empty(self) -> None:
        """A search with no matches returns an empty list."""
        self._create_payment()
        response = self.client.get(
            self.list_url, {"search": "nonexistent"},
        )
        self.assertEqual(len(response.data["results"]), 0)

    # ==================================================================
    # ORDERING
    # ==================================================================

    def test_order_by_amount_ascending(self) -> None:
        """?ordering=amount returns payments by amount ascending."""
        self._create_payment(amount="10.00")
        self._create_payment(amount="5.00")
        self._create_payment(amount="20.00")

        # Delete the newest-first ordering test payments and recreate
        Payment.objects.all().delete()
        p1 = self._create_payment(amount="5.00")
        p2 = self._create_payment(amount="10.00")
        p3 = self._create_payment(amount="20.00")

        response = self.client.get(
            self.list_url, {"ordering": "amount"},
        )
        results = response.data["results"]
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["id"], p1["id"])
        self.assertEqual(results[1]["id"], p2["id"])
        self.assertEqual(results[2]["id"], p3["id"])

    def test_order_by_amount_descending(self) -> None:
        """?ordering=-amount returns payments by amount descending."""
        Payment.objects.all().delete()
        p1 = self._create_payment(amount="5.00")
        p2 = self._create_payment(amount="10.00")
        p3 = self._create_payment(amount="20.00")

        response = self.client.get(
            self.list_url, {"ordering": "-amount"},
        )
        results = response.data["results"]
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["id"], p3["id"])
        self.assertEqual(results[1]["id"], p2["id"])
        self.assertEqual(results[2]["id"], p1["id"])

    def test_order_by_status(self) -> None:
        """?ordering=status returns payments ordered by status alphabetically."""
        Payment.objects.all().delete()
        self._create_payment(amount="10.00", status="SUCCESS")
        self._create_payment(amount="5.00", status="FAILED")
        self._create_payment(amount="20.00", status="PENDING")

        response = self.client.get(
            self.list_url, {"ordering": "status"},
        )
        results = response.data["results"]
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["status"], "FAILED")
        self.assertEqual(results[1]["status"], "PENDING")
        self.assertEqual(results[2]["status"], "SUCCESS")

    # ==================================================================
    # RETRIEVE
    # ==================================================================

    def test_retrieve_payment_returns_200(self) -> None:
        """GET /payments/<uuid>/ returns the payment."""
        data = self._create_payment()
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], data["id"])

    def test_retrieve_payment_includes_all_fields(self) -> None:
        """The detail response includes all expected fields."""
        data = self._create_payment(
            customer=str(self.customer.pk),
            provider_reference="ref_001",
            external_reference="EXT-001",
            notes="Test",
        )
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.get(detail_url)
        for field in [
            "id", "sale", "customer", "amount", "currency",
            "payment_method", "status", "provider_reference",
            "external_reference", "notes", "created_at", "updated_at",
        ]:
            self.assertIn(field, response.data)

    def test_retrieve_nonexistent_payment_returns_404(self) -> None:
        """GET /payments/<uuid>/ with non-existent UUID returns 404."""
        detail_url = reverse(
            "payments:payment-detail", args=[uuid.uuid4()],
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================================================================
    # UPDATE (PATCH)
    # ==================================================================

    def test_update_payment_status_to_success(self) -> None:
        """PATCH /payments/<uuid>/ can update status to SUCCESS."""
        data = self._create_payment()
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.patch(
            detail_url, {"status": "SUCCESS"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "SUCCESS")

    def test_update_payment_status_to_failed(self) -> None:
        """PATCH /payments/<uuid>/ can update status to FAILED."""
        data = self._create_payment()
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.patch(
            detail_url, {"status": "FAILED"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "FAILED")

    def test_update_payment_invalid_transition_returns_400(self) -> None:
        """An invalid status transition returns 400."""
        data = self._create_payment()
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        # PENDING → REFUNDED is invalid
        response = self.client.patch(
            detail_url, {"status": "REFUNDED"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_payment_notes(self) -> None:
        """PATCH can update non-status fields like notes."""
        data = self._create_payment()
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.patch(
            detail_url, {"notes": "Updated note"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["notes"], "Updated note")

    def test_update_payment_external_reference(self) -> None:
        """PATCH can update external_reference."""
        data = self._create_payment()
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.patch(
            detail_url, {"external_reference": "NEW-REF"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["external_reference"], "NEW-REF")

    # ==================================================================
    # WORKSPACE ISOLATION
    # ==================================================================

    def test_cannot_list_other_workspace_payments(self) -> None:
        """A user cannot list payments from another workspace."""
        self._create_payment()
        self._authenticate(self.other_user)
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_cannot_retrieve_other_workspace_payment(self) -> None:
        """A user gets 404 when retrieving another workspace's payment."""
        data = self._create_payment()
        self._authenticate(self.other_user)
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_update_other_workspace_payment(self) -> None:
        """A user gets 404 when updating another workspace's payment."""
        data = self._create_payment()
        self._authenticate(self.other_user)
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.patch(
            detail_url, {"notes": "Hacked"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================================================================
    # METHOD RESTRICTIONS
    # ==================================================================

    def test_delete_returns_405(self) -> None:
        """DELETE /payments/<uuid>/ returns 405."""
        data = self._create_payment()
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.delete(detail_url)
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_put_returns_405(self) -> None:
        """PUT /payments/<uuid>/ returns 405."""
        data = self._create_payment()
        detail_url = reverse("payments:payment-detail", args=[data["id"]])
        response = self.client.put(detail_url, {}, format="json")
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED,
        )
