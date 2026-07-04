"""Integration tests for the Sale API endpoints."""

import uuid

from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.inventory.models import Inventory
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem
from apps.workspaces.models import Workspace, WorkspaceMembership


class SaleAPITests(APITestCase):
    """Test all Sale API endpoints: create, list, retrieve, and method
    restrictions.

    Covers authentication, workspace isolation, business-rule
    validation (insufficient stock, missing inventory, cross-workspace
    products, invalid quantities), pagination, ordering, and inventory
    deduction.
    """

    def setUp(self) -> None:
        """Create users, workspaces, products, inventory, and
        authenticate the primary user."""
        # ------------------------------------------------------------------
        # Primary user & workspace
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # Second user & workspace (isolation tests)
        # ------------------------------------------------------------------
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            first_name="Other",
            last_name="User",
        )
        self.other_workspace = Workspace.objects.create(
            owner=self.other_user,
            name="Other Store",
            slug="other-store",
        )
        WorkspaceMembership.objects.create(
            user=self.other_user,
            workspace=self.other_workspace,
            role=WorkspaceMembership.Role.OWNER,
        )

        # ------------------------------------------------------------------
        # Products & inventory (primary workspace)
        # ------------------------------------------------------------------
        self.product = Product.objects.create(
            workspace=self.workspace,
            name="Classic T-Shirt",
            sku="TSH-001",
            cost_price="8.50",
            selling_price="19.99",
        )
        self.inventory = Inventory.objects.create(
            product=self.product, quantity=25,
        )

        self.product_b = Product.objects.create(
            workspace=self.workspace,
            name="Denim Jacket",
            sku="DNM-001",
            cost_price="35.00",
            selling_price="79.99",
        )
        self.inventory_b = Inventory.objects.create(
            product=self.product_b, quantity=10,
        )

        # Product without inventory (for missing-inventory tests)
        self.no_inv_product = Product.objects.create(
            workspace=self.workspace,
            name="No Inventory Item",
            sku="NOINV-01",
            cost_price="1.00",
            selling_price="5.00",
        )

        # ------------------------------------------------------------------
        # Product & inventory (other workspace for isolation)
        # ------------------------------------------------------------------
        self.other_product = Product.objects.create(
            workspace=self.other_workspace,
            name="Other Product",
            sku="OTH-001",
            cost_price="10.00",
            selling_price="24.99",
        )
        Inventory.objects.create(product=self.other_product, quantity=5)

        # ------------------------------------------------------------------
        # Authentication & URLs
        # ------------------------------------------------------------------
        self._authenticate(self.user)

        self.list_url = reverse("sales:sale-list")

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

    def _valid_payload(self) -> dict:
        """Return a minimal valid sale payload for a single item."""
        return {
            "items": [
                {"product": str(self.product.pk), "quantity": 2},
            ],
        }

    def _create_sale(self) -> dict:
        """Post a valid sale and return the response data."""
        response = self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        return response.data

    # ==================================================================
    # AUTHENTICATION
    # ==================================================================

    def test_unauthenticated_list_returns_401(self) -> None:
        """GET /sales/ without auth returns HTTP 401."""
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_create_returns_401(self) -> None:
        """POST /sales/ without auth returns HTTP 401."""
        self.client.credentials()
        response = self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_retrieve_returns_401(self) -> None:
        """GET /sales/<uuid>/ without auth returns HTTP 401."""
        data = self._create_sale()
        self.client.credentials()
        detail_url = reverse("sales:sale-detail", args=[data["id"]])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ==================================================================
    # CREATE SALE
    # ==================================================================

    def test_create_sale_returns_201(self) -> None:
        """POST /sales/ with valid data returns HTTP 201."""
        response = self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_sale_creates_sale_record(self) -> None:
        """A valid sale creates one Sale record in the database."""
        self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        self.assertEqual(Sale.objects.count(), 1)

    def test_create_sale_creates_sale_items(self) -> None:
        """A valid sale creates the expected number of SaleItems."""
        payload = {
            "items": [
                {"product": str(self.product.pk), "quantity": 2},
                {"product": str(self.product_b.pk), "quantity": 1},
            ],
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SaleItem.objects.count(), 2)

    def test_create_sale_deducts_inventory(self) -> None:
        """Inventory quantities are reduced after a successful sale."""
        self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 23)  # 25 - 2

    def test_create_sale_deducts_multiple_inventory(self) -> None:
        """All product inventories are reduced with multiple line items."""
        payload = {
            "items": [
                {"product": str(self.product.pk), "quantity": 3},
                {"product": str(self.product_b.pk), "quantity": 4},
            ],
        }
        self.client.post(
            self.list_url, payload, format="json"
        )
        self.inventory.refresh_from_db()
        self.inventory_b.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 22)   # 25 - 3
        self.assertEqual(self.inventory_b.quantity, 6)   # 10 - 4

    def test_create_sale_returns_subtotal(self) -> None:
        """The response includes the computed subtotal."""
        response = self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        # 2 × 19.99 = 39.98
        self.assertEqual(
            Decimal(response.data["subtotal"]), Decimal("39.98"),
        )

    def test_create_sale_returns_total(self) -> None:
        """The response includes the computed total."""
        response = self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        self.assertEqual(
            Decimal(response.data["total"]), Decimal("39.98"),
        )

    def test_create_sale_returns_expected_fields(self) -> None:
        """The response contains id, subtotal, total, created_at,
        updated_at, and items."""
        response = self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        self.assertIn("id", response.data)
        self.assertIn("subtotal", response.data)
        self.assertIn("total", response.data)
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)
        self.assertIn("items", response.data)
        self.assertIsInstance(response.data["items"], list)

    def test_create_sale_subtotal_equals_total(self) -> None:
        """For sales without discounts or taxes, subtotal equals total."""
        response = self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        self.assertEqual(
            Decimal(response.data["subtotal"]),
            Decimal(response.data["total"]),
        )

    def test_create_sale_returns_nested_items(self) -> None:
        """The response includes a nested ``items`` array."""
        response = self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        self.assertIn("items", response.data)
        self.assertIsInstance(response.data["items"], list)

    def test_create_sale_multiple_line_items(self) -> None:
        """Multiple items produce correct totals and item count."""
        # 2 × 19.99 = 39.98, 1 × 79.99 = 79.99 → subtotal = 119.97
        payload = {
            "items": [
                {"product": str(self.product.pk), "quantity": 2},
                {"product": str(self.product_b.pk), "quantity": 1},
            ],
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Decimal(response.data["subtotal"]), Decimal("119.97"),
        )
        self.assertEqual(len(response.data["items"]), 2)

    def test_create_sale_price_from_database(self) -> None:
        """The unit_price comes from the database, never the request."""
        response = self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        item = response.data["items"][0]
        # 19.99 is the selling_price stored in the DB
        self.assertEqual(Decimal(item["unit_price"]), Decimal("19.99"))

    def test_create_sale_empty_items_returns_400(self) -> None:
        """An empty ``items`` array returns HTTP 400."""
        response = self.client.post(
            self.list_url, {"items": []}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_sale_zero_quantity_returns_400(self) -> None:
        """A quantity of zero returns HTTP 400."""
        payload = {
            "items": [{"product": str(self.product.pk), "quantity": 0}],
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_sale_negative_quantity_returns_400(self) -> None:
        """A negative quantity returns HTTP 400."""
        payload = {
            "items": [{"product": str(self.product.pk), "quantity": -3}],
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_sale_nonexistent_product_returns_400(self) -> None:
        """A product UUID that does not exist returns HTTP 400."""
        payload = {
            "items": [
                {"product": str(uuid.uuid4()), "quantity": 1},
            ],
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ==================================================================
    # BUSINESS RULES
    # ==================================================================

    def test_insufficient_stock_returns_400(self) -> None:
        """Overselling available stock returns HTTP 400."""
        payload = {
            "items": [{"product": str(self.product.pk), "quantity": 999}],
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_insufficient_stock_does_not_create_sale(self) -> None:
        """No Sale is created when stock is insufficient."""
        payload = {
            "items": [{"product": str(self.product.pk), "quantity": 999}],
        }
        self.client.post(self.list_url, payload, format="json")
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)

    def test_insufficient_stock_preserves_inventory(self) -> None:
        """Inventory is unchanged after an oversell attempt."""
        payload = {
            "items": [{"product": str(self.product.pk), "quantity": 999}],
        }
        self.client.post(self.list_url, payload, format="json")
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 25)

    def test_product_without_inventory_returns_400(self) -> None:
        """A product with no inventory record returns HTTP 400."""
        payload = {
            "items": [
                {"product": str(self.no_inv_product.pk), "quantity": 1},
            ],
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_product_from_another_workspace_returns_400(self) -> None:
        """A product from another workspace returns HTTP 400."""
        payload = {
            "items": [
                {"product": str(self.other_product.pk), "quantity": 1},
            ],
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_product_from_another_workspace_does_not_create_sale(self) -> None:
        """No Sale is created when a product is from another workspace."""
        payload = {
            "items": [
                {"product": str(self.other_product.pk), "quantity": 1},
            ],
        }
        self.client.post(self.list_url, payload, format="json")
        self.assertEqual(Sale.objects.count(), 0)

    # ==================================================================
    # LIST
    # ==================================================================

    def test_list_sales_returns_200(self) -> None:
        """GET /sales/ returns HTTP 200."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_sales_is_paginated(self) -> None:
        """The list response uses the default pagination format."""
        response = self.client.get(self.list_url)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    def test_list_sales_only_own_workspace(self) -> None:
        """Only sales from the user's workspace are returned."""
        self.client.post(
            self.list_url, self._valid_payload(), format="json"
        )
        self._authenticate(self.other_user)
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_sales_newest_first(self) -> None:
        """Sales are ordered newest first (by created_at descending)."""
        sale_a = self._create_sale()
        sale_b = self._create_sale()

        response = self.client.get(self.list_url)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        # sale_b was created after sale_a
        self.assertEqual(results[0]["id"], sale_b["id"])
        self.assertEqual(results[1]["id"], sale_a["id"])

    def test_list_sales_excludes_other_workspace_sales(self) -> None:
        """A user only sees their own workspace's sales in the list."""
        self._create_sale()

        self._authenticate(self.other_user)
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 0)

        # A sale created by the other user should appear
        other_payload = {
            "items": [
                {"product": str(self.other_product.pk), "quantity": 2},
            ],
        }
        self.client.post(
            self.list_url, other_payload, format="json"
        )
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 1)

    # ==================================================================
    # RETRIEVE
    # ==================================================================

    def test_retrieve_sale_returns_200(self) -> None:
        """GET /sales/<uuid>/ returns the sale."""
        data = self._create_sale()
        detail_url = reverse("sales:sale-detail", args=[data["id"]])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_sale_includes_items(self) -> None:
        """The sale detail response includes nested line items."""
        data = self._create_sale()
        detail_url = reverse("sales:sale-detail", args=[data["id"]])
        response = self.client.get(detail_url)
        self.assertIn("items", response.data)
        self.assertEqual(len(response.data["items"]), 1)

    def test_retrieve_nonexistent_sale_returns_404(self) -> None:
        """GET /sales/<uuid>/ with a non-existent UUID returns 404."""
        detail_url = reverse("sales:sale-detail", args=[uuid.uuid4()])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_other_workspace_sale_returns_404(self) -> None:
        """A user gets 404 when retrieving another workspace's sale."""
        data = self._create_sale()
        self._authenticate(self.other_user)
        detail_url = reverse("sales:sale-detail", args=[data["id"]])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================================================================
    # METHOD RESTRICTIONS
    # ==================================================================

    def test_put_returns_405(self) -> None:
        """PUT /sales/<uuid>/ returns 405."""
        data = self._create_sale()
        detail_url = reverse("sales:sale-detail", args=[data["id"]])
        response = self.client.put(detail_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_returns_405(self) -> None:
        """PATCH /sales/<uuid>/ returns 405."""
        data = self._create_sale()
        detail_url = reverse("sales:sale-detail", args=[data["id"]])
        response = self.client.patch(detail_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_returns_405(self) -> None:
        """DELETE /sales/<uuid>/ returns 405."""
        data = self._create_sale()
        detail_url = reverse("sales:sale-detail", args=[data["id"]])
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
