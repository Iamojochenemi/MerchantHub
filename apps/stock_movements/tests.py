"""Tests for the StockMovement model, serializer, views, and service integration."""

import uuid

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.inventory.models import Inventory
from apps.inventory.services import InventoryService
from apps.products.models import Product
from apps.stock_movements.models import StockMovement
from apps.workspaces.models import Workspace, WorkspaceMembership


# ======================================================================
# Model tests
# ======================================================================


class StockMovementModelTests(TestCase):
    """Verify StockMovement model creation, fields, and constraints."""

    def setUp(self) -> None:
        """Create a user, workspace, product, and inventory record."""
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
        self.inventory = Inventory.objects.create(
            product=self.product, quantity=25,
        )

    def test_create_stock_movement(self) -> None:
        """A StockMovement can be created with valid fields."""
        movement = StockMovement.objects.create(
            inventory=self.inventory,
            movement_type=StockMovement.MovementType.RESTOCK,
            quantity=10,
            quantity_before=25,
            quantity_after=35,
            reference="PO-001",
            created_by=self.user,
        )
        self.assertIsNotNone(movement.pk)
        self.assertEqual(movement.inventory, self.inventory)
        self.assertEqual(movement.movement_type, "RESTOCK")
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.quantity_before, 25)
        self.assertEqual(movement.quantity_after, 35)
        self.assertEqual(movement.reference, "PO-001")
        self.assertEqual(movement.created_by, self.user)

    def test_movement_type_choices(self) -> None:
        """Movement type is restricted to SALE, RESTOCK, ADJUSTMENT."""
        for valid_type in ["SALE", "RESTOCK", "ADJUSTMENT"]:
            movement = StockMovement.objects.create(
                inventory=self.inventory,
                movement_type=valid_type,
                quantity=5,
                quantity_before=20,
                quantity_after=25,
            )
            self.assertEqual(movement.movement_type, valid_type)

    def test_created_by_nullable(self) -> None:
        """created_by can be null for automated processes."""
        movement = StockMovement.objects.create(
            inventory=self.inventory,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            quantity=5,
            quantity_before=20,
            quantity_after=25,
        )
        self.assertIsNone(movement.created_by)

    def test_reference_blank_by_default(self) -> None:
        """reference defaults to an empty string."""
        movement = StockMovement.objects.create(
            inventory=self.inventory,
            movement_type=StockMovement.MovementType.SALE,
            quantity=3,
            quantity_before=10,
            quantity_after=7,
        )
        self.assertEqual(movement.reference, "")

    def test_str_representation(self) -> None:
        """__str__ shows movement type, quantity, and before/after."""
        movement = StockMovement.objects.create(
            inventory=self.inventory,
            movement_type=StockMovement.MovementType.RESTOCK,
            quantity=10,
            quantity_before=25,
            quantity_after=35,
        )
        result = str(movement)
        self.assertIn("Restock", result)
        self.assertIn("10", result)
        self.assertIn("25", result)
        self.assertIn("35", result)

    def test_ordering_newest_first(self) -> None:
        """Movements are ordered by created_at descending."""
        m1 = StockMovement.objects.create(
            inventory=self.inventory,
            movement_type="RESTOCK",
            quantity=5,
            quantity_before=10,
            quantity_after=15,
        )
        m2 = StockMovement.objects.create(
            inventory=self.inventory,
            movement_type="SALE",
            quantity=3,
            quantity_before=15,
            quantity_after=12,
        )
        qs = StockMovement.objects.all()
        self.assertEqual(qs[0], m2)
        self.assertEqual(qs[1], m1)

    def test_cascade_on_inventory_delete(self) -> None:
        """Deleting the inventory cascades to its stock movements."""
        StockMovement.objects.create(
            inventory=self.inventory,
            movement_type="RESTOCK",
            quantity=10,
            quantity_before=25,
            quantity_after=35,
        )
        self.inventory.delete()
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_created_by_set_null_on_user_delete(self) -> None:
        """Deleting a user sets created_by to null (SET_NULL)."""
        movement = StockMovement.objects.create(
            inventory=self.inventory,
            movement_type="RESTOCK",
            quantity=5,
            quantity_before=10,
            quantity_after=15,
            created_by=self.user,
        )
        # Transfer workspace ownership so the user can be deleted
        # without a ProtectedError on Workspace.owner.
        stand_in = User.objects.create_user(
            email="standin@example.com",
            password="testpass123",
        )
        self.workspace.owner = stand_in
        self.workspace.save()

        self.user.delete()
        movement.refresh_from_db()
        self.assertIsNone(movement.created_by)


# ======================================================================
# Service integration tests
# ======================================================================


class StockMovementServiceIntegrationTests(TestCase):
    """Verify that InventoryService methods automatically create
    StockMovement records with correct before/after snapshots."""

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
        self.inventory = Inventory.objects.create(
            product=self.product, quantity=50,
        )

    # ------------------------------------------------------------------
    # increase_stock (RESTOCK)
    # ------------------------------------------------------------------

    def test_increase_stock_creates_restock_movement(self) -> None:
        """increase_stock creates a RESTOCK movement."""
        InventoryService.increase_stock(
            inventory=self.inventory,
            quantity=10,
            created_by=self.user,
            reference="PO-001",
        )
        movements = StockMovement.objects.filter(inventory=self.inventory)
        self.assertEqual(movements.count(), 1)
        movement = movements.first()
        self.assertEqual(movement.movement_type, "RESTOCK")
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.created_by, self.user)
        self.assertEqual(movement.reference, "PO-001")

    def test_increase_stock_saves_before_after_quantity(self) -> None:
        """Before and after quantities are recorded correctly."""
        InventoryService.increase_stock(
            inventory=self.inventory,
            quantity=10,
        )
        movement = StockMovement.objects.first()
        self.assertEqual(movement.quantity_before, 50)
        self.assertEqual(movement.quantity_after, 60)

    def test_increase_stock_without_optional_args(self) -> None:
        """increase_stock works without created_by and reference (backward compat)."""
        InventoryService.increase_stock(
            inventory=self.inventory,
            quantity=5,
        )
        movement = StockMovement.objects.first()
        self.assertIsNone(movement.created_by)
        self.assertEqual(movement.reference, "")

    # ------------------------------------------------------------------
    # decrease_stock (SALE)
    # ------------------------------------------------------------------

    def test_decrease_stock_creates_sale_movement(self) -> None:
        """decrease_stock creates a SALE movement."""
        InventoryService.decrease_stock(
            inventory=self.inventory,
            quantity=3,
            created_by=self.user,
            reference="Sale #123",
        )
        movement = StockMovement.objects.first()
        self.assertEqual(movement.movement_type, "SALE")
        self.assertEqual(movement.quantity, 3)
        self.assertEqual(movement.created_by, self.user)
        self.assertEqual(movement.reference, "Sale #123")

    def test_decrease_stock_saves_before_after_quantity(self) -> None:
        """Before and after are recorded correctly for decreases."""
        InventoryService.decrease_stock(
            inventory=self.inventory,
            quantity=8,
        )
        movement = StockMovement.objects.first()
        self.assertEqual(movement.quantity_before, 50)
        self.assertEqual(movement.quantity_after, 42)

    def test_decrease_stock_insufficient_stock_does_not_create_movement(self) -> None:
        """An oversell error does not create a StockMovement."""
        from rest_framework.exceptions import ValidationError

        try:
            InventoryService.decrease_stock(
                inventory=self.inventory,
                quantity=999,
            )
        except ValidationError:
            pass
        self.assertEqual(StockMovement.objects.count(), 0)

    # ------------------------------------------------------------------
    # adjust_stock (ADJUSTMENT)
    # ------------------------------------------------------------------

    def test_adjust_stock_creates_adjustment_movement(self) -> None:
        """adjust_stock creates an ADJUSTMENT movement."""
        InventoryService.adjust_stock(
            inventory=self.inventory,
            quantity=100,
            created_by=self.user,
            reference="Manual adjustment",
        )
        movement = StockMovement.objects.first()
        self.assertEqual(movement.movement_type, "ADJUSTMENT")
        self.assertEqual(movement.quantity, 100)
        self.assertEqual(movement.created_by, self.user)
        self.assertEqual(movement.reference, "Manual adjustment")

    def test_adjust_stock_saves_before_after_quantity(self) -> None:
        """Before and after are recorded correctly for adjustments."""
        InventoryService.adjust_stock(
            inventory=self.inventory,
            quantity=25,
        )
        movement = StockMovement.objects.first()
        self.assertEqual(movement.quantity_before, 50)
        self.assertEqual(movement.quantity_after, 25)

    def test_adjust_stock_to_zero_creates_movement(self) -> None:
        """Adjusting stock to zero still creates a movement."""
        InventoryService.adjust_stock(
            inventory=self.inventory,
            quantity=0,
        )
        movement = StockMovement.objects.first()
        self.assertEqual(movement.quantity_before, 50)
        self.assertEqual(movement.quantity_after, 0)
        self.assertEqual(movement.movement_type, "ADJUSTMENT")

    def test_adjust_stock_invalid_quantity_does_not_create_movement(self) -> None:
        """A negative adjustment does not create a StockMovement."""
        from rest_framework.exceptions import ValidationError

        try:
            InventoryService.adjust_stock(
                inventory=self.inventory,
                quantity=-1,
            )
        except ValidationError:
            pass
        self.assertEqual(StockMovement.objects.count(), 0)

    # ------------------------------------------------------------------
    # Multiple movements accumulate
    # ------------------------------------------------------------------

    def test_multiple_movements_are_recorded(self) -> None:
        """Multiple stock operations create multiple movement records."""
        InventoryService.increase_stock(
            inventory=self.inventory, quantity=10,
        )
        InventoryService.decrease_stock(
            inventory=self.inventory, quantity=5,
        )
        InventoryService.adjust_stock(
            inventory=self.inventory, quantity=30,
        )
        self.assertEqual(StockMovement.objects.count(), 3)

    def test_movements_ordered_newest_first(self) -> None:
        """Multiple movements are ordered by created_at descending."""
        InventoryService.increase_stock(
            inventory=self.inventory, quantity=10,
        )
        InventoryService.decrease_stock(
            inventory=self.inventory, quantity=5,
        )
        qs = StockMovement.objects.all()
        # The last operation should be first
        self.assertEqual(qs[0].movement_type, "SALE")
        self.assertEqual(qs[1].movement_type, "RESTOCK")


# ======================================================================
# Serializer tests
# ======================================================================


class StockMovementSerializerTests(APITestCase):
    """Verify StockMovementSerializer output format."""

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
        self.inventory = Inventory.objects.create(
            product=self.product, quantity=50,
        )

    def test_serialized_output_contains_expected_fields(self) -> None:
        """The serialized output includes all specified fields."""
        movement = InventoryService.increase_stock(
            inventory=self.inventory,
            quantity=10,
            created_by=self.user,
            reference="PO-001",
        )
        from apps.stock_movements.serializers import StockMovementSerializer

        # Fetch the movement that was created
        stock_movement = StockMovement.objects.get(inventory=self.inventory)
        serializer = StockMovementSerializer(stock_movement)
        data = serializer.data

        self.assertIn("id", data)
        self.assertIn("inventory", data)
        self.assertIn("movement_type", data)
        self.assertIn("quantity", data)
        self.assertIn("quantity_before", data)
        self.assertIn("quantity_after", data)
        self.assertIn("reference", data)
        self.assertIn("created_by", data)
        self.assertIn("created_at", data)

    def test_serialized_values_match_model(self) -> None:
        """The serialized values match the model fields."""
        InventoryService.increase_stock(
            inventory=self.inventory,
            quantity=15,
            created_by=self.user,
            reference="PO-002",
        )
        from apps.stock_movements.serializers import StockMovementSerializer

        stock_movement = StockMovement.objects.get(inventory=self.inventory)
        serializer = StockMovementSerializer(stock_movement)
        data = serializer.data

        self.assertEqual(data["movement_type"], "RESTOCK")
        self.assertEqual(data["quantity"], 15)
        self.assertEqual(data["quantity_before"], 50)
        self.assertEqual(data["quantity_after"], 65)
        self.assertEqual(data["reference"], "PO-002")
        self.assertEqual(data["created_by"], str(self.user.pk))


# ======================================================================
# View tests
# ======================================================================


class StockMovementAPITests(APITestCase):
    """Test the StockMovement API endpoints."""

    def setUp(self) -> None:
        # --- Primary user & workspace ---
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

        # --- Second user & workspace (isolation tests) ---
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

        # --- Products & inventory ---
        self.product = Product.objects.create(
            workspace=self.workspace,
            name="Test Product",
            sku="TST-001",
            cost_price="5.00",
            selling_price="12.99",
        )
        self.inventory = Inventory.objects.create(
            product=self.product, quantity=50,
        )

        self.other_product = Product.objects.create(
            workspace=self.other_workspace,
            name="Other Product",
            sku="OTH-001",
            cost_price="10.00",
            selling_price="24.99",
        )
        self.other_inventory = Inventory.objects.create(
            product=self.other_product, quantity=30,
        )

        # --- Create stock movements for both workspaces ---
        self._authenticate(self.user)
        InventoryService.increase_stock(
            inventory=self.inventory,
            quantity=10,
            reference="First restock",
        )
        InventoryService.decrease_stock(
            inventory=self.inventory,
            quantity=3,
            reference="Sale #1",
        )

        # Create movements in the other workspace
        self._authenticate(self.other_user)
        InventoryService.increase_stock(
            inventory=self.other_inventory,
            quantity=20,
            reference="Other restock",
        )

        # --- Authentication & URLs ---
        self._authenticate(self.user)
        self.list_url = reverse("stock_movements:stockmovement-list")

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

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def test_unauthenticated_list_returns_401(self) -> None:
        """GET /stock-movements/ without auth returns 401."""
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_retrieve_returns_401(self) -> None:
        """GET /stock-movements/<uuid>/ without auth returns 401."""
        movement = StockMovement.objects.filter(
            inventory=self.inventory,
        ).first()
        self.client.credentials()
        detail_url = reverse(
            "stock_movements:stockmovement-detail",
            args=[movement.pk],
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 401)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def test_list_returns_200(self) -> None:
        """GET /stock-movements/ returns 200."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_list_is_paginated(self) -> None:
        """The list response uses pagination."""
        response = self.client.get(self.list_url)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    def test_list_returns_only_own_workspace(self) -> None:
        """Only movements from the user's workspace are returned."""
        response = self.client.get(self.list_url)
        results = response.data["results"]
        # Our workspace has 2 movements (restock + sale)
        self.assertEqual(len(results), 2)

    def test_list_newest_first(self) -> None:
        """Movements are ordered newest first."""
        response = self.client.get(self.list_url)
        results = response.data["results"]
        # The second movement (sale) should be first
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["movement_type"], "SALE")
        self.assertEqual(results[1]["movement_type"], "RESTOCK")

    def test_list_excludes_other_workspace(self) -> None:
        """A user cannot see movements from another workspace."""
        self._authenticate(self.other_user)
        response = self.client.get(self.list_url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["reference"], "Other restock")

    def test_list_returns_serialized_fields(self) -> None:
        """Each result contains all expected fields."""
        response = self.client.get(self.list_url)
        result = response.data["results"][0]
        self.assertIn("id", result)
        self.assertIn("inventory", result)
        self.assertIn("movement_type", result)
        self.assertIn("quantity", result)
        self.assertIn("quantity_before", result)
        self.assertIn("quantity_after", result)
        self.assertIn("reference", result)
        self.assertIn("created_by", result)
        self.assertIn("created_at", result)

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    def test_retrieve_returns_200(self) -> None:
        """GET /stock-movements/<uuid>/ returns the movement."""
        movement = StockMovement.objects.filter(
            inventory=self.inventory,
        ).first()
        detail_url = reverse(
            "stock_movements:stockmovement-detail",
            args=[movement.pk],
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        # First movement by default ordering is newest first (Sale #1)
        self.assertEqual(response.data["reference"], "Sale #1")

    def test_retrieve_nonexistent_returns_404(self) -> None:
        """GET with a non-existent UUID returns 404."""
        detail_url = reverse(
            "stock_movements:stockmovement-detail",
            args=[uuid.uuid4()],
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404)

    def test_retrieve_other_workspace_returns_404(self) -> None:
        """A user gets 404 when retrieving another workspace's movement."""
        movement = StockMovement.objects.filter(
            inventory=self.other_inventory,
        ).first()
        self._authenticate(self.user)
        detail_url = reverse(
            "stock_movements:stockmovement-detail",
            args=[movement.pk],
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Method restrictions
    # ------------------------------------------------------------------

    def test_post_returns_405(self) -> None:
        """POST /stock-movements/ returns 405."""
        response = self.client.post(
            self.list_url, {}, format="json"
        )
        self.assertEqual(response.status_code, 405)

    def test_put_returns_405(self) -> None:
        """PUT /stock-movements/<uuid>/ returns 405."""
        movement = StockMovement.objects.filter(
            inventory=self.inventory,
        ).first()
        detail_url = reverse(
            "stock_movements:stockmovement-detail",
            args=[movement.pk],
        )
        response = self.client.put(detail_url, {}, format="json")
        self.assertEqual(response.status_code, 405)

    def test_patch_returns_405(self) -> None:
        """PATCH /stock-movements/<uuid>/ returns 405."""
        movement = StockMovement.objects.filter(
            inventory=self.inventory,
        ).first()
        detail_url = reverse(
            "stock_movements:stockmovement-detail",
            args=[movement.pk],
        )
        response = self.client.patch(detail_url, {}, format="json")
        self.assertEqual(response.status_code, 405)

    def test_delete_returns_405(self) -> None:
        """DELETE /stock-movements/<uuid>/ returns 405."""
        movement = StockMovement.objects.filter(
            inventory=self.inventory,
        ).first()
        detail_url = reverse(
            "stock_movements:stockmovement-detail",
            args=[movement.pk],
        )
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, 405)
