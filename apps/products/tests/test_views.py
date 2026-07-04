"""Integration tests for the Product API endpoints."""

import uuid

from django.urls import reverse
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.products.models import Product
from apps.workspaces.models import Workspace, WorkspaceMembership


class ProductAPITests(APITestCase):
    """Test all Product API endpoints."""

    def setUp(self) -> None:
        """Create a user, workspace, membership, and authenticate."""
        # --- User & workspace setup ---
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

        # --- Second workspace for isolation tests ---
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

        # --- Authenticate as the first user ---
        self._authenticate(self.user)

        # --- URLs ---
        self.list_url = reverse("products:product-list")

        # --- Valid payload ---
        self.valid_payload = {
            "name": "Classic T-Shirt",
            "sku": "TSH-001",
            "description": "A comfortable cotton t-shirt.",
            "cost_price": "8.50",
            "selling_price": "19.99",
        }

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

    def _create_product(
        self, **overrides: str
    ) -> tuple[dict, Product]:
        """Post a valid product and return the response data + instance."""
        payload = {**self.valid_payload, **overrides}
        response = self.client.post(self.list_url, payload, format="json")
        product = Product.objects.get(
            workspace=self.workspace,
            sku=payload.get("sku", self.valid_payload["sku"]),
        )
        return response.data, product

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def test_create_product_returns_201(self) -> None:
        """A valid payload returns HTTP 201 with the product data."""
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_product_returns_all_fields(self) -> None:
        """The response includes all serialized product fields."""
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertIn("id", data)
        self.assertEqual(data["name"], self.valid_payload["name"])
        self.assertEqual(data["sku"], self.valid_payload["sku"])
        self.assertEqual(
            data["description"], self.valid_payload["description"]
        )
        self.assertEqual(data["cost_price"], self.valid_payload["cost_price"])
        self.assertEqual(
            data["selling_price"], self.valid_payload["selling_price"]
        )
        self.assertTrue(data["is_active"])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_create_product_sets_correct_workspace(self) -> None:
        """The product is scoped to the authenticated user's workspace."""
        self.client.post(self.list_url, self.valid_payload, format="json")
        product = Product.objects.get(
            workspace=self.workspace, sku=self.valid_payload["sku"]
        )
        self.assertEqual(product.workspace, self.workspace)

    def test_create_product_without_description(self) -> None:
        """Description is optional — omitting it stores an empty string."""
        payload = {k: v for k, v in self.valid_payload.items() if k != "description"}
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["description"], "")

    def test_create_product_missing_required_fields_returns_400(self) -> None:
        """Omitting required fields returns HTTP 400."""
        required_fields = ["name", "sku", "cost_price", "selling_price"]
        for field in required_fields:
            payload = {
                k: v
                for k, v in self.valid_payload.items()
                if k != field
            }
            with self.subTest(missing=field):
                response = self.client.post(
                    self.list_url, payload, format="json"
                )
                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def test_list_products_returns_200(self) -> None:
        """GET /products/ returns HTTP 200."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_products_returns_only_active(self) -> None:
        """Inactive (archived) products are excluded from the list."""
        self._create_product()
        self._create_product(sku="TSH-002", name="V-Neck T-Shirt")

        # Archive the first product
        detail_url = reverse(
            "products:product-detail", args=[Product.objects.get(sku="TSH-001").pk]
        )
        self.client.delete(detail_url)

        response = self.client.get(self.list_url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["sku"], "TSH-002")

    def test_list_products_is_paginated(self) -> None:
        """The list response uses the default pagination format."""
        response = self.client.get(self.list_url)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def test_retrieve_product_returns_200(self) -> None:
        """GET /products/<uuid>/ returns the product."""
        _, product = self._create_product()
        detail_url = reverse("products:product-detail", args=[product.pk])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sku"], product.sku)

    def test_retrieve_nonexistent_product_returns_404(self) -> None:
        """GET /products/<uuid>/ with a non-existent UUID returns 404."""
        detail_url = reverse(
            "products:product-detail", args=[uuid.uuid4()]
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------
    # Update (PATCH)
    # ------------------------------------------------------------------

    def test_partial_update_returns_200(self) -> None:
        """PATCH /products/<uuid>/ updates the product and returns it."""
        _, product = self._create_product()
        detail_url = reverse("products:product-detail", args=[product.pk])
        response = self.client.patch(
            detail_url, {"name": "Updated T-Shirt"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated T-Shirt")

        # Verify database was updated
        product.refresh_from_db()
        self.assertEqual(product.name, "Updated T-Shirt")

    def test_partial_update_preserves_other_fields(self) -> None:
        """Updating one field does not affect other fields."""
        _, product = self._create_product()
        detail_url = reverse("products:product-detail", args=[product.pk])
        self.client.patch(
            detail_url, {"name": "Updated T-Shirt"}, format="json"
        )
        product.refresh_from_db()
        self.assertEqual(product.sku, "TSH-001")
        self.assertEqual(product.selling_price, Decimal("19.99"))

    # ------------------------------------------------------------------
    # Soft delete (archive)
    # ------------------------------------------------------------------

    def test_delete_archives_product_returns_200(self) -> None:
        """DELETE /products/<uuid>/ archives and returns 200 with the product."""
        _, product = self._create_product()
        detail_url = reverse("products:product-detail", args=[product.pk])
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify soft-delete in the database
        product.refresh_from_db()
        self.assertFalse(product.is_active)

    def test_deleted_product_excluded_from_list(self) -> None:
        """Archived products no longer appear in the list."""
        _, product = self._create_product()
        detail_url = reverse("products:product-detail", args=[product.pk])
        self.client.delete(detail_url)

        response = self.client.get(self.list_url)
        results = response.data["results"]
        ids = [p["id"] for p in results]
        self.assertNotIn(str(product.pk), ids)

    def test_deleted_product_returns_404_on_retrieve(self) -> None:
        """Archived products return 404 on GET."""
        _, product = self._create_product()
        detail_url = reverse("products:product-detail", args=[product.pk])
        self.client.delete(detail_url)
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------
    # Duplicate SKU rejection
    # ------------------------------------------------------------------

    def test_duplicate_sku_in_same_workspace_returns_400(self) -> None:
        """Creating a product with an existing SKU in the same workspace
        returns HTTP 400."""
        self.client.post(self.list_url, self.valid_payload, format="json")
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_sku_different_workspace_allowed(self) -> None:
        """The same SKU is allowed in different workspaces."""
        self.client.post(self.list_url, self.valid_payload, format="json")

        # Authenticate as the other user
        self._authenticate(self.other_user)
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update_sku_to_duplicate_returns_400(self) -> None:
        """Updating a product's SKU to one already used in the workspace
        returns HTTP 400."""
        self._create_product(sku="TSH-001")
        _, product_b = self._create_product(
            sku="TSH-002", name="V-Neck T-Shirt"
        )

        detail_url = reverse(
            "products:product-detail", args=[product_b.pk]
        )
        response = self.client.patch(
            detail_url, {"sku": "TSH-001"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_sku_to_own_sku_is_allowed(self) -> None:
        """Updating a product without changing its SKU is allowed."""
        _, product = self._create_product()
        detail_url = reverse("products:product-detail", args=[product.pk])
        response = self.client.patch(
            detail_url,
            {"name": "Still Same SKU"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # Workspace isolation
    # ------------------------------------------------------------------

    def test_cannot_list_other_workspace_products(self) -> None:
        """A user cannot list products from another workspace."""
        # Create a product in the first workspace
        self._create_product()

        # Authenticate as the other user
        self._authenticate(self.other_user)
        response = self.client.get(self.list_url)
        results = response.data["results"]
        self.assertEqual(len(results), 0)

    def test_cannot_retrieve_other_workspace_product(self) -> None:
        """A user gets 404 when retrieving another workspace's product."""
        _, product = self._create_product()
        self._authenticate(self.other_user)
        detail_url = reverse(
            "products:product-detail", args=[product.pk]
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_update_other_workspace_product(self) -> None:
        """A user gets 404 when updating another workspace's product."""
        _, product = self._create_product()
        self._authenticate(self.other_user)
        detail_url = reverse(
            "products:product-detail", args=[product.pk]
        )
        response = self.client.patch(
            detail_url, {"name": "Hacked Name"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_other_workspace_product(self) -> None:
        """A user gets 404 when deleting another workspace's product."""
        _, product = self._create_product()
        self._authenticate(self.other_user)
        detail_url = reverse(
            "products:product-detail", args=[product.pk]
        )
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def test_unauthenticated_create_returns_401(self) -> None:
        """POST /products/ without auth returns HTTP 401."""
        self.client.credentials()
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_list_returns_401(self) -> None:
        """GET /products/ without auth returns HTTP 401."""
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_retrieve_returns_401(self) -> None:
        """GET /products/<uuid>/ without auth returns HTTP 401."""
        _, product = self._create_product()
        self.client.credentials()
        detail_url = reverse(
            "products:product-detail", args=[product.pk]
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_update_returns_401(self) -> None:
        """PATCH /products/<uuid>/ without auth returns HTTP 401."""
        _, product = self._create_product()
        self.client.credentials()
        detail_url = reverse(
            "products:product-detail", args=[product.pk]
        )
        response = self.client.patch(
            detail_url, {"name": "Hacked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_delete_returns_401(self) -> None:
        """DELETE /products/<uuid>/ without auth returns HTTP 401."""
        _, product = self._create_product()
        self.client.credentials()
        detail_url = reverse(
            "products:product-detail", args=[product.pk]
        )
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
