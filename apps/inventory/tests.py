"""Tests for ``InventoryService``."""

from django.test import TestCase

from apps.inventory.models import Inventory
from apps.inventory.services import InventoryService


class InventoryServiceTests(TestCase):
    """Verify the business rules enforced by ``InventoryService``."""

    def setUp(self) -> None:
        """Create a product and its inventory record."""
        from apps.accounts.models import User
        from apps.products.models import Product
        from apps.workspaces.models import Workspace, WorkspaceMembership

        user = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            first_name="Jane",
            last_name="Doe",
        )
        workspace = Workspace.objects.create(
            owner=user, name="Test Store", slug="test-store"
        )
        WorkspaceMembership.objects.create(
            user=user, workspace=workspace, role=WorkspaceMembership.Role.OWNER
        )

        self.product = Product.objects.create(
            workspace=workspace,
            name="Test Product",
            sku="TST-001",
            cost_price="5.00",
            selling_price="12.99",
        )

        self.inventory = Inventory.objects.create(
            product=self.product, quantity=10
        )

    # ------------------------------------------------------------------
    # increase_stock
    # ------------------------------------------------------------------

    def test_increase_stock_adds_quantity(self) -> None:
        """Increasing stock adds the given quantity to the current value."""
        result = InventoryService.increase_stock(
            inventory=self.inventory, quantity=5
        )
        self.assertEqual(result.quantity, 15)
        self.assertEqual(result, self.inventory)

    def test_increase_stock_from_zero(self) -> None:
        """Increasing stock works when the current quantity is zero."""
        self.inventory.quantity = 0
        self.inventory.save(update_fields=["quantity"])

        result = InventoryService.increase_stock(
            inventory=self.inventory, quantity=3
        )
        self.assertEqual(result.quantity, 3)

    def test_increase_stock_saves_only_quantity_and_updated_at(self) -> None:
        """Only ``quantity`` and ``updated_at`` are written to the DB."""
        original_created = self.inventory.created_at

        InventoryService.increase_stock(
            inventory=self.inventory, quantity=5
        )
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 15)
        self.assertEqual(self.inventory.created_at, original_created)

    # ------------------------------------------------------------------
    # decrease_stock
    # ------------------------------------------------------------------

    def test_decrease_stock_removes_quantity(self) -> None:
        """Decreasing stock deducts the given quantity."""
        result = InventoryService.decrease_stock(
            inventory=self.inventory, quantity=3
        )
        self.assertEqual(result.quantity, 7)
        self.assertEqual(result, self.inventory)

    def test_decrease_stock_to_zero(self) -> None:
        """Decreasing stock to exactly zero is allowed."""
        result = InventoryService.decrease_stock(
            inventory=self.inventory, quantity=10
        )
        self.assertEqual(result.quantity, 0)

    def test_decrease_stock_saves_only_quantity_and_updated_at(self) -> None:
        """Only ``quantity`` and ``updated_at`` are written to the DB."""
        original_created = self.inventory.created_at

        InventoryService.decrease_stock(
            inventory=self.inventory, quantity=3
        )
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 7)
        self.assertEqual(self.inventory.created_at, original_created)

    # ------------------------------------------------------------------
    # Insufficient stock (decrease_stock)
    # ------------------------------------------------------------------

    def test_decrease_insufficient_stock_raises_error(self) -> None:
        """Decreasing more than available stock raises ``ValidationError``."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as cm:
            InventoryService.decrease_stock(
                inventory=self.inventory, quantity=15
            )
        self.assertIn("Insufficient stock", str(cm.exception.detail))

    def test_decrease_insufficient_stock_does_not_change_quantity(self) -> None:
        """After an insufficient-stock error, the quantity is unchanged."""
        from rest_framework.exceptions import ValidationError

        original_qty = self.inventory.quantity
        try:
            InventoryService.decrease_stock(
                inventory=self.inventory, quantity=999
            )
        except ValidationError:
            pass
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, original_qty)

    # ------------------------------------------------------------------
    # adjust_stock
    # ------------------------------------------------------------------

    def test_adjust_stock_sets_exact_quantity(self) -> None:
        """Adjustment sets the quantity to the exact value given."""
        result = InventoryService.adjust_stock(
            inventory=self.inventory, quantity=25
        )
        self.assertEqual(result.quantity, 25)

    def test_adjust_stock_to_zero(self) -> None:
        """Adjusting stock to zero is allowed."""
        result = InventoryService.adjust_stock(
            inventory=self.inventory, quantity=0
        )
        self.assertEqual(result.quantity, 0)

    def test_adjust_stock_saves_only_quantity_and_updated_at(self) -> None:
        """Only ``quantity`` and ``updated_at`` are written to the DB."""
        original_created = self.inventory.created_at

        InventoryService.adjust_stock(
            inventory=self.inventory, quantity=50
        )
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 50)
        self.assertEqual(self.inventory.created_at, original_created)

    # ------------------------------------------------------------------
    # Invalid quantities (all methods)
    # ------------------------------------------------------------------

    def test_increase_with_zero_raises_error(self) -> None:
        """Increasing by zero raises ``ValidationError``."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            InventoryService.increase_stock(
                inventory=self.inventory, quantity=0
            )

    def test_increase_with_negative_raises_error(self) -> None:
        """Increasing by a negative number raises ``ValidationError``."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            InventoryService.increase_stock(
                inventory=self.inventory, quantity=-5
            )

    def test_decrease_with_zero_raises_error(self) -> None:
        """Decreasing by zero raises ``ValidationError``."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            InventoryService.decrease_stock(
                inventory=self.inventory, quantity=0
            )

    def test_decrease_with_negative_raises_error(self) -> None:
        """Decreasing by a negative number raises ``ValidationError``."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            InventoryService.decrease_stock(
                inventory=self.inventory, quantity=-3
            )

    def test_adjust_with_negative_raises_error(self) -> None:
        """Adjusting to a negative quantity raises ``ValidationError``."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            InventoryService.adjust_stock(
                inventory=self.inventory, quantity=-1
            )

    def test_increase_with_non_integer_raises_error(self) -> None:
        """Increasing by a non-integer value raises ``ValidationError``."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            InventoryService.increase_stock(
                inventory=self.inventory, quantity=1.5  # type: ignore[arg-type]
            )

    def test_decrease_with_non_integer_raises_error(self) -> None:
        """Decreasing by a non-integer value raises ``ValidationError``."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            InventoryService.decrease_stock(
                inventory=self.inventory, quantity="abc"  # type: ignore[arg-type]
            )

    def test_adjust_with_non_integer_raises_error(self) -> None:
        """Adjusting with a non-integer value raises ``ValidationError``."""
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            InventoryService.adjust_stock(
                inventory=self.inventory, quantity=None  # type: ignore[arg-type]
            )
