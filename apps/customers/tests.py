"""
Comprehensive tests for the Customer model, serializer, and API.

Covers model creation, serialization, full CRUD, workspace
isolation, authentication, search, pagination, validations
(duplicate phone, required fields), and method restrictions.
"""

import uuid

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.workspaces.models import Workspace, WorkspaceMembership


# ======================================================================
# Model tests
# ======================================================================


class CustomerModelTests(APITestCase):
    """Verify Customer model creation, fields, and constraints."""

    def setUp(self) -> None:
        """Create a user, workspace, and workspace membership."""
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

    def test_create_customer(self) -> None:
        """A Customer can be created with valid fields."""
        customer = Customer.objects.create(
            workspace=self.workspace,
            first_name="John",
            last_name="Doe",
            phone_number="+1234567890",
            email="john@example.com",
            address="123 Main St",
            notes="VIP customer",
        )
        self.assertIsNotNone(customer.pk)
        self.assertEqual(customer.first_name, "John")
        self.assertEqual(customer.last_name, "Doe")
        self.assertEqual(customer.phone_number, "+1234567890")
        self.assertEqual(customer.email, "john@example.com")
        self.assertEqual(customer.address, "123 Main St")
        self.assertEqual(customer.notes, "VIP customer")

    def test_customer_with_minimal_fields(self) -> None:
        """A Customer requires only first_name and phone_number."""
        customer = Customer.objects.create(
            workspace=self.workspace,
            first_name="Alice",
            phone_number="+9876543210",
        )
        self.assertIsNotNone(customer.pk)
        self.assertEqual(customer.last_name, "")
        self.assertIsNone(customer.email)
        self.assertEqual(customer.address, "")
        self.assertEqual(customer.notes, "")

    def test_unique_phone_per_workspace(self) -> None:
        """Duplicate phone within the same workspace raises an error."""
        Customer.objects.create(
            workspace=self.workspace,
            first_name="John",
            phone_number="+1234567890",
        )
        with self.assertRaises(Exception):
            Customer.objects.create(
                workspace=self.workspace,
                first_name="Jane",
                phone_number="+1234567890",
            )

    def test_same_phone_different_workspace_allowed(self) -> None:
        """The same phone number is allowed in different workspaces."""
        other_workspace = Workspace.objects.create(
            owner=self.user,
            name="Other Store",
            slug="other-store",
        )
        Customer.objects.create(
            workspace=self.workspace,
            first_name="John",
            phone_number="+1234567890",
        )
        customer = Customer.objects.create(
            workspace=other_workspace,
            first_name="John",
            phone_number="+1234567890",
        )
        self.assertIsNotNone(customer.pk)

    def test_str_representation(self) -> None:
        """__str__ returns 'First Last' or just first_name."""
        with_last = Customer.objects.create(
            workspace=self.workspace,
            first_name="John",
            last_name="Doe",
            phone_number="+11111",
        )
        self.assertEqual(str(with_last), "John Doe")

        without_last = Customer.objects.create(
            workspace=self.workspace,
            first_name="Alice",
            phone_number="+22222",
        )
        self.assertEqual(str(without_last), "Alice")

    def test_ordering_newest_first(self) -> None:
        """Customers are ordered by created_at descending."""
        c1 = Customer.objects.create(
            workspace=self.workspace,
            first_name="Old",
            phone_number="+11111",
        )
        c2 = Customer.objects.create(
            workspace=self.workspace,
            first_name="New",
            phone_number="+22222",
        )
        qs = Customer.objects.all()
        self.assertEqual(qs[0], c2)
        self.assertEqual(qs[1], c1)

    def test_cascade_on_workspace_delete(self) -> None:
        """Deleting a workspace cascades to its customers."""
        Customer.objects.create(
            workspace=self.workspace,
            first_name="John",
            phone_number="+1234567890",
        )
        self.workspace.delete()
        self.assertEqual(Customer.objects.count(), 0)


# ======================================================================
# Serializer tests
# ======================================================================


class CustomerSerializerTests(APITestCase):
    """Verify CustomerSerializer output and validation."""

    def setUp(self) -> None:
        """Create a user, workspace, membership, and authenticate."""
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

        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )

        self.list_url = reverse("customers:customer-list")
        self.valid_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "phone_number": "+1234567890",
            "email": "john@example.com",
            "address": "123 Main St",
            "notes": "VIP",
        }

    def test_serialized_output_contains_expected_fields(self) -> None:
        """The serialized output includes all public fields."""
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertIn("id", data)
        self.assertIn("first_name", data)
        self.assertIn("last_name", data)
        self.assertIn("phone_number", data)
        self.assertIn("email", data)
        self.assertIn("address", data)
        self.assertIn("notes", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
        # Workspace must never be exposed
        self.assertNotIn("workspace", data)

    def test_serialized_values_match_input(self) -> None:
        """The serialized values match the input data."""
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        data = response.data
        self.assertEqual(data["first_name"], "John")
        self.assertEqual(data["last_name"], "Doe")
        self.assertEqual(data["phone_number"], "+1234567890")
        self.assertEqual(data["email"], "john@example.com")
        self.assertEqual(data["address"], "123 Main St")
        self.assertEqual(data["notes"], "VIP")


# ======================================================================
# View / API tests
# ======================================================================


class CustomerAPITests(APITestCase):
    """Test all Customer API endpoints — CRUD, auth, isolation,
    search, pagination, and validation."""

    def setUp(self) -> None:
        """Create users, workspaces, memberships, and authenticate."""
        # --- Primary user & workspace ---
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

        # --- Second user & workspace (isolation tests) ---
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

        # --- Authentication & URLs ---
        self._authenticate(self.user)

        self.list_url = reverse("customers:customer-list")

        # --- Valid payload ---
        self.valid_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "phone_number": "+1234567890",
            "email": "john@example.com",
            "address": "123 Main St",
            "notes": "VIP customer",
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

    def _create_customer(
        self, **overrides: str
    ) -> tuple[dict, Customer]:
        """Post a valid customer and return the response data + instance."""
        payload = {**self.valid_payload, **overrides}
        response = self.client.post(self.list_url, payload, format="json")
        customer = Customer.objects.get(
            workspace=self.workspace,
            phone_number=payload.get(
                "phone_number", self.valid_payload["phone_number"]
            ),
        )
        return response.data, customer

    # ==================================================================
    # AUTHENTICATION
    # ==================================================================

    def test_unauthenticated_create_returns_401(self) -> None:
        """POST /customers/ without auth returns HTTP 401."""
        self.client.credentials()
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_list_returns_401(self) -> None:
        """GET /customers/ without auth returns HTTP 401."""
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_retrieve_returns_401(self) -> None:
        """GET /customers/<uuid>/ without auth returns HTTP 401."""
        data, _ = self._create_customer()
        self.client.credentials()
        detail_url = reverse("customers:customer-detail", args=[data["id"]])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_update_returns_401(self) -> None:
        """PATCH /customers/<uuid>/ without auth returns HTTP 401."""
        data, _ = self._create_customer()
        self.client.credentials()
        detail_url = reverse("customers:customer-detail", args=[data["id"]])
        response = self.client.patch(
            detail_url, {"first_name": "Hacked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_delete_returns_401(self) -> None:
        """DELETE /customers/<uuid>/ without auth returns HTTP 401."""
        data, _ = self._create_customer()
        self.client.credentials()
        detail_url = reverse("customers:customer-detail", args=[data["id"]])
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ==================================================================
    # CREATE
    # ==================================================================

    def test_create_customer_returns_201(self) -> None:
        """A valid payload returns HTTP 201 with the customer data."""
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_customer_sets_correct_workspace(self) -> None:
        """The customer is scoped to the authenticated user's workspace."""
        self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        customer = Customer.objects.get(
            workspace=self.workspace,
            phone_number=self.valid_payload["phone_number"],
        )
        self.assertEqual(customer.workspace, self.workspace)

    def test_create_customer_minimal_fields(self) -> None:
        """Only first_name and phone_number are required."""
        payload = {
            "first_name": "Alice",
            "phone_number": "+9876543210",
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["first_name"], "Alice")
        self.assertEqual(response.data["last_name"], "")
        self.assertIsNone(response.data.get("email"))
        self.assertEqual(response.data["address"], "")
        self.assertEqual(response.data["notes"], "")

    def test_create_customer_missing_first_name_returns_400(self) -> None:
        """Omitting first_name returns HTTP 400."""
        payload = {
            "phone_number": "+1234567890",
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_customer_missing_phone_returns_400(self) -> None:
        """Omitting phone_number returns HTTP 400."""
        payload = {
            "first_name": "John",
        }
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_customer_rejects_extra_fields(self) -> None:
        """Extra fields like workspace are silently ignored."""
        payload = {**self.valid_payload, "workspace": str(uuid.uuid4())}
        response = self.client.post(
            self.list_url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ==================================================================
    # DUPLICATE PHONE
    # ==================================================================

    def test_duplicate_phone_in_same_workspace_returns_400(self) -> None:
        """Creating a customer with an existing phone returns 400."""
        self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_phone_different_workspace_allowed(self) -> None:
        """The same phone is allowed in a different workspace."""
        self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self._authenticate(self.other_user)
        response = self.client.post(
            self.list_url, self.valid_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update_phone_to_existing_returns_400(self) -> None:
        """Updating a customer's phone to an existing one returns 400."""
        self._create_customer(phone_number="+11111")
        _, customer_b = self._create_customer(
            phone_number="+22222",
            first_name="Alice",
        )
        detail_url = reverse(
            "customers:customer-detail", args=[customer_b.pk]
        )
        response = self.client.patch(
            detail_url,
            {"phone_number": "+11111"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_phone_to_own_phone_allowed(self) -> None:
        """Keeping the same phone number on update is allowed."""
        data, customer = self._create_customer()
        detail_url = reverse(
            "customers:customer-detail", args=[customer.pk]
        )
        response = self.client.patch(
            detail_url,
            {"first_name": "Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["phone_number"], self.valid_payload["phone_number"]
        )

    # ==================================================================
    # LIST
    # ==================================================================

    def test_list_customers_returns_200(self) -> None:
        """GET /customers/ returns HTTP 200."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_customers_is_paginated(self) -> None:
        """The list response uses the default pagination format."""
        response = self.client.get(self.list_url)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    def test_list_customers_newest_first(self) -> None:
        """Customers are ordered newest first."""
        data_a, _ = self._create_customer(phone_number="+11111")
        data_b, _ = self._create_customer(phone_number="+22222")

        response = self.client.get(self.list_url)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], data_b["id"])
        self.assertEqual(results[1]["id"], data_a["id"])

    def test_list_customers_only_own_workspace(self) -> None:
        """Only customers from the user's workspace are returned."""
        self._create_customer()
        self._authenticate(self.other_user)
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_customers_excludes_other_workspace(self) -> None:
        """A user can only see their own workspace's customers."""
        self._create_customer()

        self._authenticate(self.other_user)
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 0)

        # Create a customer in the other workspace
        other_payload = {
            "first_name": "Bob",
            "phone_number": "+99999",
        }
        self.client.post(self.list_url, other_payload, format="json")
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 1)

    # ==================================================================
    # SEARCH
    # ==================================================================

    def test_search_by_first_name(self) -> None:
        """?search= filters by first_name."""
        self._create_customer(phone_number="+11111", first_name="Alice")
        self._create_customer(phone_number="+22222", first_name="Bob")

        response = self.client.get(
            self.list_url, {"search": "Alice"}
        )
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "Alice")

    def test_search_by_last_name(self) -> None:
        """?search= filters by last_name."""
        self._create_customer(
            phone_number="+11111",
            first_name="Alice",
            last_name="Johnson",
        )
        self._create_customer(
            phone_number="+22222",
            first_name="Bob",
            last_name="Smith",
        )

        response = self.client.get(
            self.list_url, {"search": "Johnson"}
        )
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["last_name"], "Johnson")

    def test_search_by_phone_number(self) -> None:
        """?search= filters by phone_number."""
        self._create_customer(phone_number="+11111", first_name="Alice")
        self._create_customer(phone_number="+22222", first_name="Bob")

        response = self.client.get(
            self.list_url, {"search": "11111"}
        )
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["phone_number"], "+11111")

    def test_search_by_email(self) -> None:
        """?search= filters by email."""
        self._create_customer(
            phone_number="+11111",
            first_name="Alice",
            email="alice@example.com",
        )
        self._create_customer(
            phone_number="+22222",
            first_name="Bob",
            email="bob@test.com",
        )

        response = self.client.get(
            self.list_url, {"search": "alice@example.com"}
        )
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["email"], "alice@example.com")

    def test_search_no_match_returns_empty(self) -> None:
        """A search with no matches returns an empty list."""
        self._create_customer(first_name="Alice")
        response = self.client.get(
            self.list_url, {"search": "nonexistent"}
        )
        self.assertEqual(len(response.data["results"]), 0)

    # ==================================================================
    # RETRIEVE
    # ==================================================================

    def test_retrieve_customer_returns_200(self) -> None:
        """GET /customers/<uuid>/ returns the customer."""
        data, customer = self._create_customer()
        detail_url = reverse("customers:customer-detail", args=[customer.pk])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], customer.first_name)

    def test_retrieve_nonexistent_customer_returns_404(self) -> None:
        """GET /customers/<uuid>/ with a non-existent UUID returns 404."""
        detail_url = reverse(
            "customers:customer-detail", args=[uuid.uuid4()]
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================================================================
    # UPDATE (PATCH)
    # ==================================================================

    def test_partial_update_returns_200(self) -> None:
        """PATCH /customers/<uuid>/ updates the customer and returns it."""
        data, customer = self._create_customer()
        detail_url = reverse("customers:customer-detail", args=[customer.pk])
        response = self.client.patch(
            detail_url,
            {"first_name": "Jane"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Jane")

        customer.refresh_from_db()
        self.assertEqual(customer.first_name, "Jane")

    def test_partial_update_preserves_other_fields(self) -> None:
        """Updating one field does not affect others."""
        data, customer = self._create_customer()
        detail_url = reverse("customers:customer-detail", args=[customer.pk])
        self.client.patch(
            detail_url,
            {"first_name": "Jane"},
            format="json",
        )
        customer.refresh_from_db()
        self.assertEqual(customer.last_name, "Doe")
        self.assertEqual(customer.phone_number, "+1234567890")

    # ==================================================================
    # DELETE
    # ==================================================================

    def test_delete_returns_204(self) -> None:
        """DELETE /customers/<uuid>/ removes the customer and returns 204."""
        data, customer = self._create_customer()
        detail_url = reverse("customers:customer-detail", args=[customer.pk])
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Customer.objects.filter(pk=customer.pk).exists()
        )

    def test_delete_nonexistent_returns_404(self) -> None:
        """DELETE /customers/<uuid>/ with a non-existent UUID returns 404."""
        detail_url = reverse(
            "customers:customer-detail", args=[uuid.uuid4()]
        )
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================================================================
    # WORKSPACE ISOLATION
    # ==================================================================

    def test_cannot_list_other_workspace_customers(self) -> None:
        """A user cannot list customers from another workspace."""
        self._create_customer()
        self._authenticate(self.other_user)
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_cannot_retrieve_other_workspace_customer(self) -> None:
        """A user gets 404 when retrieving another workspace's customer."""
        data, customer = self._create_customer()
        self._authenticate(self.other_user)
        detail_url = reverse(
            "customers:customer-detail", args=[customer.pk]
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_update_other_workspace_customer(self) -> None:
        """A user gets 404 when updating another workspace's customer."""
        data, customer = self._create_customer()
        self._authenticate(self.other_user)
        detail_url = reverse(
            "customers:customer-detail", args=[customer.pk]
        )
        response = self.client.patch(
            detail_url,
            {"first_name": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_other_workspace_customer(self) -> None:
        """A user gets 404 when deleting another workspace's customer."""
        data, customer = self._create_customer()
        self._authenticate(self.other_user)
        detail_url = reverse(
            "customers:customer-detail", args=[customer.pk]
        )
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================================================================
    # FULL UPDATE (PUT)
    # ==================================================================

    def test_full_update_returns_200(self) -> None:
        """PUT /customers/<uuid>/ with a full payload updates and
        returns the customer."""
        data, customer = self._create_customer()
        detail_url = reverse(
            "customers:customer-detail", args=[customer.pk]
        )
        payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "phone_number": "+1234567890",
            "email": "jane@example.com",
            "address": "456 Oak St",
            "notes": "Updated notes",
        }
        response = self.client.put(detail_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Jane")
        self.assertEqual(response.data["last_name"], "Smith")

        customer.refresh_from_db()
        self.assertEqual(customer.first_name, "Jane")
        self.assertEqual(customer.last_name, "Smith")
        self.assertEqual(customer.address, "456 Oak St")

    def test_full_update_requires_all_required_fields(self) -> None:
        """PUT /customers/<uuid>/ without required fields returns 400."""
        data, customer = self._create_customer()
        detail_url = reverse(
            "customers:customer-detail", args=[customer.pk]
        )
        # PUT without first_name should fail
        response = self.client.put(
            detail_url, {"phone_number": "+99999"}, format="json"
        )
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST
        )
