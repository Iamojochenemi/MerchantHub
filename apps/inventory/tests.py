"""Tests for ``InventoryService`` and Inventory API endpoints."""

import uuid

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.inventory.models import Inventory
from apps.inventory.services import InventoryService
from apps.products.models import Product
from apps.workspaces.models import Workspace, WorkspaceMembership


class InventoryServiceTests(TestCase):
    """Verify the business rules enforced by ``InventoryService``."""

    def setUp(self) -> None:
        """Create a product and its inventory record."""
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


class InventoryAPITests(APITestCase):
    """Test the Inventory API endpoints."""

    def setUp(self) -> None:
        """Create users, workspaces, products, and inventory records."""
        # --- Primary user ---
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

        # --- Second user for isolation tests ---
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            first_name="Other",
            last_name="User",
        )
        self.other_workspace = Workspace.objects.create(
            owner=self.other_user, name="Other Store", slug="other-store"
        )
        WorkspaceMembership.objects.create(
            user=self.other_user,
            workspace=self.other_workspace,
            role=WorkspaceMembership.Role.OWNER,
        )

        # --- Products and inventory ---
        self.product = Product.objects.create(
            workspace=self.workspace,
            name="Test Product",
            sku="TST-001",
            cost_price="5.00",
            selling_price="12.99",
        )
        self.inventory = Inventory.objects.create(
            product=self.product, quantity=10
        )

        # Second product in the same workspace
        self.product2 = Product.objects.create(
            workspace=self.workspace,
            name="Second Product",
            sku="TST-002",
            cost_price="3.00",
            selling_price="7.99",
        )
        self.inventory2 = Inventory.objects.create(
            product=self.product2, quantity=25
        )

        # Product in the other workspace
        self.other_product = Product.objects.create(
            workspace=self.other_workspace,
            name="Other Product",
            sku="OTH-001",
            cost_price="10.00",
            selling_price="24.99",
        )
        self.other_inventory = Inventory.objects.create(
            product=self.other_product, quantity=5
        )

        # --- Authentication ---
        self._authenticate(self.user)

        # --- URLs ---
        self.list_url = reverse("inventory:inventory-list")
        self.detail_url = reverse(
            "inventory:inventory-detail", args=[self.inventory.pk]
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _authenticate(self, user: User) -> None:
        """Set authentication credentials on the test client."""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def test_list_inventory_returns_200(self) -> None:
        """GET /inventory/ returns HTTP 200."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_list_inventory_returns_only_own_workspace(self) -> None:
        """Only inventory in the user's workspace is listed."""
        response = self.client.get(self.list_url)
        results = response.data["results"]
        self.assertEqual(len(results), 2)

    def test_list_inventory_is_paginated(self) -> None:
        """The list response uses the pagination format."""
        response = self.client.get(self.list_url)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    def test_retrieve_inventory_returns_200(self) -> None:
        """GET /inventory/<uuid>/ returns the inventory record."""
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quantity"], 10)

    def test_retrieve_nonexistent_inventory_returns_404(self) -> None:
        """GET /inventory/<uuid>/ with a non-existent UUID returns 404."""
        url = reverse("inventory:inventory-detail", args=[uuid.uuid4()])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Patch (adjust quantity)
    # ------------------------------------------------------------------

    def test_patch_quantity_returns_200(self) -> None:
        """PATCH /inventory/<uuid>/ with a valid quantity returns 200."""
        response = self.client.patch(
            self.detail_url, {"quantity": 50}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quantity"], 50)

    def test_patch_quantity_updates_database(self) -> None:
        """PATCH updates the database record."""
        self.client.patch(
            self.detail_url, {"quantity": 100}, format="json"
        )
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 100)

    def test_patch_quantity_to_zero(self) -> None:
        """PATCH setting quantity to zero is allowed."""
        response = self.client.patch(
            self.detail_url, {"quantity": 0}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quantity"], 0)

    def test_patch_negative_quantity_returns_400(self) -> None:
        """PATCH with a negative quantity returns 400."""
        response = self.client.patch(
            self.detail_url, {"quantity": -5}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_without_quantity_is_noop(self) -> None:
        """PATCH without quantity field leaves the record unchanged."""
        response = self.client.patch(
            self.detail_url, {"product": str(self.product.pk)}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quantity"], 10)

    # ------------------------------------------------------------------
    # Method restrictions
    # ------------------------------------------------------------------

    def test_delete_returns_405(self) -> None:
        """DELETE is not allowed on inventory detail."""
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, 405)

    def test_post_returns_405_on_list(self) -> None:
        """POST is not allowed on inventory list."""
        response = self.client.post(self.list_url, {"quantity": 5}, format="json")
        self.assertEqual(response.status_code, 405)

    # ------------------------------------------------------------------
    # Workspace isolation
    # ------------------------------------------------------------------

    def test_cannot_list_other_workspace_inventory(self) -> None:
        """A user cannot see inventory from another workspace."""
        self._authenticate(self.other_user)
        response = self.client.get(self.list_url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(
            str(results[0]["product"]), str(self.other_product.pk)
        )

    def test_cannot_retrieve_other_workspace_inventory(self) -> None:
        """A user gets 404 when retrieving another workspace's inventory."""
        self._authenticate(self.other_user)
        url = reverse(
            "inventory:inventory-detail", args=[self.inventory.pk]
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_cannot_patch_other_workspace_inventory(self) -> None:
        """A user gets 404 when patching another workspace's inventory."""
        self._authenticate(self.other_user)
        url = reverse(
            "inventory:inventory-detail", args=[self.inventory.pk]
        )
        response = self.client.patch(
            url, {"quantity": 99}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def test_unauthenticated_list_returns_401(self) -> None:
        """GET /inventory/ without auth returns 401."""
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_retrieve_returns_401(self) -> None:
        """GET /inventory/<uuid>/ without auth returns 401."""
        self.client.credentials()
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_patch_returns_401(self) -> None:
        """PATCH /inventory/<uuid>/ without auth returns 401."""
        self.client.credentials()
        response = self.client.patch(
            self.detail_url, {"quantity": 5}, format="json"
        )
        self.assertEqual(response.status_code, 401)
