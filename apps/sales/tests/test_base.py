"""Tests for the Sale and SaleItem models, SalesService, and serializers."""

from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.inventory.models import Inventory
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem
from apps.sales.services import SalesService
from apps.workspaces.models import Workspace, WorkspaceMembership


# ======================================================================
# Model tests
# ======================================================================


class SaleModelTests(TestCase):
    """Verify Sale model creation, relationships, and constraints."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            first_name="Jane",
            last_name="Doe",
        )
        self.workspace = Workspace.objects.create(
            owner=self.user, name="Test Store", slug="test-store"
        )
        WorkspaceMembership.objects.create(
            user=self.user,
            workspace=self.workspace,
            role=WorkspaceMembership.Role.OWNER,
        )

    def test_create_sale(self) -> None:
        """A Sale can be created with valid fields."""
        sale = Sale.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            subtotal=Decimal("19.99"),
            total=Decimal("21.49"),
        )
        self.assertIsNotNone(sale.pk)
        self.assertEqual(sale.workspace, self.workspace)
        self.assertEqual(sale.created_by, self.user)
        self.assertEqual(sale.subtotal, Decimal("19.99"))
        self.assertEqual(sale.total, Decimal("21.49"))

    def test_sale_str(self) -> None:
        """__str__ contains the pk and total."""
        sale = Sale.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            subtotal=Decimal("10.00"),
            total=Decimal("10.00"),
        )
        self.assertIn(str(sale.pk), str(sale))
        self.assertIn("10.00", str(sale))

    def test_sale_ordering(self) -> None:
        """Sales are ordered by created_at descending."""
        sale1 = Sale.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            subtotal=Decimal("10.00"),
            total=Decimal("10.00"),
        )
        sale2 = Sale.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            subtotal=Decimal("20.00"),
            total=Decimal("20.00"),
        )
        qs = Sale.objects.all()
        self.assertEqual(qs[0], sale2)
        self.assertEqual(qs[1], sale1)

    def test_sale_negative_subtotal_raises_integrity_error(self) -> None:
        """A sale with a negative subtotal violates the CheckConstraint."""
        with self.assertRaises(IntegrityError):
            Sale.objects.create(
                workspace=self.workspace,
                created_by=self.user,
                subtotal=Decimal("-1.00"),
                total=Decimal("10.00"),
            )

    def test_sale_negative_total_raises_integrity_error(self) -> None:
        """A sale with a negative total violates the CheckConstraint."""
        with self.assertRaises(IntegrityError):
            Sale.objects.create(
                workspace=self.workspace,
                created_by=self.user,
                subtotal=Decimal("10.00"),
                total=Decimal("-1.00"),
            )

    def test_sale_zero_subtotal_allowed(self) -> None:
        """A subtotal of zero is allowed (free items or discounts)."""
        sale = Sale.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            subtotal=Decimal("0.00"),
            total=Decimal("0.00"),
        )
        self.assertEqual(sale.subtotal, Decimal("0.00"))

    def test_sale_cascade_on_workspace_delete(self) -> None:
        """Deleting the workspace cascades to its sales."""
        Sale.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            subtotal=Decimal("10.00"),
            total=Decimal("10.00"),
        )
        self.workspace.delete()
        self.assertEqual(Sale.objects.count(), 0)


class SaleItemModelTests(TestCase):
    """Verify SaleItem model creation, relationships, and constraints."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            first_name="Jane",
            last_name="Doe",
        )
        self.workspace = Workspace.objects.create(
            owner=self.user, name="Test Store", slug="test-store"
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
        self.sale = Sale.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            subtotal=Decimal("25.98"),
            total=Decimal("25.98"),
        )

    def test_create_sale_item(self) -> None:
        """A SaleItem can be created with valid fields."""
        item = SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=2,
            unit_price=Decimal("12.99"),
            line_total=Decimal("25.98"),
        )
        self.assertIsNotNone(item.pk)
        self.assertEqual(item.sale, self.sale)
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("12.99"))
        self.assertEqual(item.line_total, Decimal("25.98"))

    def test_sale_item_str(self) -> None:
        """__str__ shows product, quantity, and unit price."""
        item = SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=3,
            unit_price=Decimal("12.99"),
            line_total=Decimal("38.97"),
        )
        self.assertIn(self.product.sku, str(item))
        self.assertIn("3", str(item))
        self.assertIn("12.99", str(item))

    def test_sale_item_zero_quantity_raises_integrity_error(self) -> None:
        """A SaleItem with zero quantity violates the CheckConstraint."""
        with self.assertRaises(IntegrityError):
            SaleItem.objects.create(
                sale=self.sale,
                product=self.product,
                quantity=0,
                unit_price=Decimal("12.99"),
                line_total=Decimal("0.00"),
            )

    def test_sale_item_negative_unit_price_raises_integrity_error(self) -> None:
        """A SaleItem with a negative unit price violates the CheckConstraint."""
        with self.assertRaises(IntegrityError):
            SaleItem.objects.create(
                sale=self.sale,
                product=self.product,
                quantity=1,
                unit_price=Decimal("-5.00"),
                line_total=Decimal("-5.00"),
            )

    def test_sale_item_negative_line_total_raises_integrity_error(self) -> None:
        """A SaleItem with a negative line total violates the CheckConstraint."""
        with self.assertRaises(IntegrityError):
            SaleItem.objects.create(
                sale=self.sale,
                product=self.product,
                quantity=1,
                unit_price=Decimal("10.00"),
                line_total=Decimal("-1.00"),
            )

    def test_sale_item_zero_unit_price_allowed(self) -> None:
        """A unit price of zero is allowed (free items)."""
        item = SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal("0.00"),
            line_total=Decimal("0.00"),
        )
        self.assertEqual(item.unit_price, Decimal("0.00"))

    def test_sale_item_cascade_on_sale_delete(self) -> None:
        """Deleting the sale cascades to its items."""
        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal("12.99"),
            line_total=Decimal("12.99"),
        )
        self.sale.delete()
        self.assertEqual(SaleItem.objects.count(), 0)

    def test_sale_item_product_protected_on_delete(self) -> None:
        """Deleting a product used in a SaleItem raises ProtectedError."""
        from django.db.models.deletion import ProtectedError

        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal("12.99"),
            line_total=Decimal("12.99"),
        )
        with self.assertRaises(ProtectedError):
            self.product.delete()

    def test_sale_related_name_items(self) -> None:
        """Access items through the sale's related_name."""
        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=2,
            unit_price=Decimal("12.99"),
            line_total=Decimal("25.98"),
        )
        self.assertEqual(self.sale.items.count(), 1)


# ======================================================================
# Service tests
# ======================================================================


class SalesServiceTests(TestCase):
    """Verify ``SalesService.create_sale()`` business rules."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            first_name="Jane",
            last_name="Doe",
        )
        self.workspace = Workspace.objects.create(
            owner=self.user, name="Test Store", slug="test-store"
        )
        WorkspaceMembership.objects.create(
            user=self.user,
            workspace=self.workspace,
            role=WorkspaceMembership.Role.OWNER,
        )

        self.product_a = Product.objects.create(
            workspace=self.workspace,
            name="Product A",
            sku="PRD-A",
            cost_price="2.00",
            selling_price="9.99",
        )
        self.product_b = Product.objects.create(
            workspace=self.workspace,
            name="Product B",
            sku="PRD-B",
            cost_price="5.00",
            selling_price="14.99",
        )

        self.inv_a = Inventory.objects.create(
            product=self.product_a, quantity=20
        )
        self.inv_b = Inventory.objects.create(
            product=self.product_b, quantity=15
        )

        self.other_workspace = Workspace.objects.create(
            owner=self.user, name="Other Store", slug="other-store"
        )
        self.other_product = Product.objects.create(
            workspace=self.other_workspace,
            name="Other Product",
            sku="OTH-001",
            cost_price="8.00",
            selling_price="19.99",
        )
        Inventory.objects.create(product=self.other_product, quantity=10)

        self.no_inv_product = Product.objects.create(
            workspace=self.workspace,
            name="No Inventory",
            sku="NOINV-01",
            cost_price="1.00",
            selling_price="5.00",
        )

    def test_create_sale_creates_sale_and_items(self) -> None:
        """A valid sale creates a Sale with the correct totals."""
        sale = SalesService.create_sale(
            workspace=self.workspace,
            created_by=self.user,
            items=[
                {"product": self.product_a, "quantity": 2},
                {"product": self.product_b, "quantity": 3},
            ],
        )
        self.assertIsNotNone(sale.pk)
        self.assertEqual(sale.workspace, self.workspace)
        self.assertEqual(sale.created_by, self.user)
        self.assertEqual(sale.subtotal, Decimal("64.95"))
        self.assertEqual(sale.total, Decimal("64.95"))

    def test_create_sale_creates_correct_number_of_items(self) -> None:
        """Each item dict results in one SaleItem."""
        sale = SalesService.create_sale(
            workspace=self.workspace,
            created_by=self.user,
            items=[
                {"product": self.product_a, "quantity": 1},
                {"product": self.product_b, "quantity": 2},
            ],
        )
        self.assertEqual(sale.items.count(), 2)

    def test_create_sale_uses_db_price_not_client_value(self) -> None:
        """The unit_price comes from the database, never the client."""
        sale = SalesService.create_sale(
            workspace=self.workspace,
            created_by=self.user,
            items=[{"product": self.product_a, "quantity": 1}],
        )
        item = sale.items.get()
        self.assertEqual(item.unit_price, Decimal("9.99"))

    def test_create_sale_reduces_inventory(self) -> None:
        """Stock is reduced by the quantity sold."""
        SalesService.create_sale(
            workspace=self.workspace,
            created_by=self.user,
            items=[{"product": self.product_a, "quantity": 3}],
        )
        self.inv_a.refresh_from_db()
        self.assertEqual(self.inv_a.quantity, 17)

    def test_create_sale_insufficient_stock_raises_error(self) -> None:
        """A sale that would oversell raises ValidationError."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as cm:
            SalesService.create_sale(
                workspace=self.workspace,
                created_by=self.user,
                items=[{"product": self.product_a, "quantity": 999}],
            )
        self.assertIn("Insufficient stock", str(cm.exception))

    def test_create_sale_insufficient_stock_rolls_back(self) -> None:
        """After an oversell error, no sale or item is created."""
        from rest_framework.exceptions import ValidationError

        original_count = Sale.objects.count()

        try:
            SalesService.create_sale(
                workspace=self.workspace,
                created_by=self.user,
                items=[{"product": self.product_a, "quantity": 999}],
            )
        except ValidationError:
            pass

        self.assertEqual(Sale.objects.count(), original_count)
        self.assertEqual(SaleItem.objects.count(), 0)

    def test_create_sale_insufficient_stock_preserves_inventory(self) -> None:
        """Inventory is unchanged after an oversell error."""
        from rest_framework.exceptions import ValidationError

        original_qty = self.inv_a.quantity

        try:
            SalesService.create_sale(
                workspace=self.workspace,
                created_by=self.user,
                items=[{"product": self.product_a, "quantity": 999}],
            )
        except ValidationError:
            pass

        self.inv_a.refresh_from_db()
        self.assertEqual(self.inv_a.quantity, original_qty)

    def test_create_sale_wrong_workspace_raises_error(self) -> None:
        """A product from a different workspace raises ValidationError."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as cm:
            SalesService.create_sale(
                workspace=self.workspace,
                created_by=self.user,
                items=[{"product": self.other_product, "quantity": 1}],
            )
        self.assertIn("does not belong", str(cm.exception))

    def test_create_sale_wrong_workspace_rolls_back(self) -> None:
        """No sale is created when a product is from the wrong workspace."""
        from rest_framework.exceptions import ValidationError

        try:
            SalesService.create_sale(
                workspace=self.workspace,
                created_by=self.user,
                items=[{"product": self.other_product, "quantity": 1}],
            )
        except ValidationError:
            pass

        self.assertEqual(Sale.objects.count(), 0)

    def test_create_sale_zero_quantity_raises_error(self) -> None:
        """A quantity of zero raises ValidationError."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            SalesService.create_sale(
                workspace=self.workspace,
                created_by=self.user,
                items=[{"product": self.product_a, "quantity": 0}],
            )

    def test_create_sale_negative_quantity_raises_error(self) -> None:
        """A negative quantity raises ValidationError."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            SalesService.create_sale(
                workspace=self.workspace,
                created_by=self.user,
                items=[{"product": self.product_a, "quantity": -1}],
            )

    def test_create_sale_invalid_quantity_rolls_back(self) -> None:
        """No sale is created when quantity is invalid."""
        from rest_framework.exceptions import ValidationError

        try:
            SalesService.create_sale(
                workspace=self.workspace,
                created_by=self.user,
                items=[{"product": self.product_a, "quantity": 0}],
            )
        except ValidationError:
            pass

        self.assertEqual(Sale.objects.count(), 0)

    def test_create_sale_no_inventory_record_raises_error(self) -> None:
        """A product without an inventory record raises ValidationError."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as cm:
            SalesService.create_sale(
                workspace=self.workspace,
                created_by=self.user,
                items=[
                    {"product": self.no_inv_product, "quantity": 1}
                ],
            )
        self.assertIn("No inventory record", str(cm.exception))

    def test_create_sale_no_inventory_rolls_back(self) -> None:
        """No sale is created when a product lacks an inventory record."""
        from rest_framework.exceptions import ValidationError

        try:
            SalesService.create_sale(
                workspace=self.workspace,
                created_by=self.user,
                items=[
                    {"product": self.no_inv_product, "quantity": 1}
                ],
            )
        except ValidationError:
            pass

        self.assertEqual(Sale.objects.count(), 0)


# ======================================================================
# Serializer tests
# ======================================================================


class SaleSerializerTests(APITestCase):
    """Verify ``SaleSerializer`` input validation and output format."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            first_name="Jane",
            last_name="Doe",
        )
        self.workspace = Workspace.objects.create(
            owner=self.user, name="Test Store", slug="test-store"
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
        Inventory.objects.create(product=self.product, quantity=10)

        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        self.request = factory.post("/api/v1/sales/")
        self.request.user = self.user

    def _get_context(self) -> dict:
        return {"request": self.request}

    def test_valid_payload_accepts_items(self) -> None:
        """A valid payload with items passes serializer validation."""
        from apps.sales.serializers import SaleSerializer

        serializer = SaleSerializer(
            data={
                "items": [
                    {"product": self.product.pk, "quantity": 2},
                ],
            },
            context=self._get_context(),
        )
        self.assertTrue(serializer.is_valid(), msg=serializer.errors)

    def test_valid_payload_rejects_extra_fields(self) -> None:
        """``workspace``, ``created_by``, ``subtotal``, ``total`` are ignored."""
        from apps.sales.serializers import SaleSerializer

        serializer = SaleSerializer(
            data={
                "items": [{"product": self.product.pk, "quantity": 1}],
                "workspace": str(self.workspace.pk),
                "created_by": str(self.user.pk),
                "subtotal": "100.00",
                "total": "100.00",
            },
            context=self._get_context(),
        )
        self.assertTrue(serializer.is_valid(), msg=serializer.errors)

    def test_empty_items_returns_error(self) -> None:
        """An empty items list fails validation."""
        from apps.sales.serializers import SaleSerializer

        serializer = SaleSerializer(
            data={"items": []},
            context=self._get_context(),
        )
        self.assertFalse(serializer.is_valid())

    def test_missing_items_returns_error(self) -> None:
        """Omitting items entirely fails validation."""
        from apps.sales.serializers import SaleSerializer

        serializer = SaleSerializer(
            data={},
            context=self._get_context(),
        )
        self.assertFalse(serializer.is_valid())

    def test_item_without_product_returns_error(self) -> None:
        """An item dict without a product fails validation."""
        from apps.sales.serializers import SaleSerializer

        serializer = SaleSerializer(
            data={"items": [{"quantity": 1}]},
            context=self._get_context(),
        )
        self.assertFalse(serializer.is_valid())

    def test_item_without_quantity_returns_error(self) -> None:
        """An item dict without a quantity fails validation."""
        from apps.sales.serializers import SaleSerializer

        serializer = SaleSerializer(
            data={"items": [{"product": self.product.pk}]},
            context=self._get_context(),
        )
        self.assertFalse(serializer.is_valid())

    def test_item_zero_quantity_returns_error(self) -> None:
        """A quantity of zero fails validation."""
        from apps.sales.serializers import SaleSerializer

        serializer = SaleSerializer(
            data={
                "items": [{"product": self.product.pk, "quantity": 0}],
            },
            context=self._get_context(),
        )
        self.assertFalse(serializer.is_valid())

    def test_item_negative_quantity_returns_error(self) -> None:
        """A negative quantity fails validation."""
        from apps.sales.serializers import SaleSerializer

        serializer = SaleSerializer(
            data={
                "items": [{"product": self.product.pk, "quantity": -1}],
            },
            context=self._get_context(),
        )
        self.assertFalse(serializer.is_valid())

    def test_item_nonexistent_product_returns_error(self) -> None:
        """A non-existent product UUID fails validation."""
        import uuid

        from apps.sales.serializers import SaleSerializer

        serializer = SaleSerializer(
            data={
                "items": [
                    {"product": uuid.uuid4(), "quantity": 1},
                ],
            },
            context=self._get_context(),
        )
        self.assertFalse(serializer.is_valid())

    def test_serialized_output_contains_expected_fields(self) -> None:
        """The serialized output includes id, subtotal, total, timestamps, items."""
        from apps.sales.serializers import SaleSerializer

        sale = SalesService.create_sale(
            workspace=self.workspace,
            created_by=self.user,
            items=[{"product": self.product, "quantity": 2}],
        )

        serializer = SaleSerializer(
            instance=sale, context=self._get_context()
        )
        data = serializer.data
        self.assertIn("id", data)
        self.assertIn("subtotal", data)
        self.assertIn("total", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
        self.assertIn("items", data)

    def test_serialized_output_has_correct_totals(self) -> None:
        """Totals in the output match the computed values."""
        from apps.sales.serializers import SaleSerializer

        sale = SalesService.create_sale(
            workspace=self.workspace,
            created_by=self.user,
            items=[{"product": self.product, "quantity": 3}],
        )

        serializer = SaleSerializer(
            instance=sale, context=self._get_context()
        )
        data = serializer.data
        self.assertEqual(Decimal(data["subtotal"]), Decimal("38.97"))
        self.assertEqual(Decimal(data["total"]), Decimal("38.97"))

    def test_serialized_items_contain_line_item_fields(self) -> None:
        """Each item in the output has product, quantity, unit_price, line_total."""
        from apps.sales.serializers import SaleSerializer

        sale = SalesService.create_sale(
            workspace=self.workspace,
            created_by=self.user,
            items=[{"product": self.product, "quantity": 2}],
        )

        serializer = SaleSerializer(
            instance=sale, context=self._get_context()
        )
        items = serializer.data["items"]
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertIn("product", item)
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(Decimal(item["unit_price"]), Decimal("12.99"))
        self.assertEqual(Decimal(item["line_total"]), Decimal("25.98"))
