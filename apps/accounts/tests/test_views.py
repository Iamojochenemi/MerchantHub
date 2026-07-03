"""Integration tests for the registration endpoint."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.workspaces.models import BusinessProfile, Workspace, WorkspaceMembership


class RegistrationViewTests(APITestCase):
    """Test ``POST /api/v1/auth/register/``."""

    def setUp(self) -> None:
        self.url = reverse("accounts:register")
        self.valid_payload = {
            "email": "merchant@example.com",
            "password": "secure-pass-123",
            "first_name": "Jane",
            "last_name": "Doe",
        }

    def test_successful_registration_returns_201(self) -> None:
        """A valid payload returns HTTP 201."""
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_successful_registration_creates_all_models(self) -> None:
        """Registration creates exactly one User, Workspace, BusinessProfile,
        and WorkspaceMembership, all correctly linked."""
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Counts
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Workspace.objects.count(), 1)
        self.assertEqual(BusinessProfile.objects.count(), 1)
        self.assertEqual(WorkspaceMembership.objects.count(), 1)

        # Relationships
        user = User.objects.get()
        workspace = user.owned_workspaces.get()
        self.assertEqual(workspace.owner, user)

        profile = workspace.business_profile
        self.assertIsNotNone(profile)
        self.assertEqual(profile.workspace, workspace)

        membership = workspace.memberships.get()
        self.assertEqual(membership.user, user)
        self.assertEqual(membership.workspace, workspace)
        self.assertEqual(membership.role, WorkspaceMembership.Role.OWNER)

    def test_duplicate_email_returns_400(self) -> None:
        """Registering with an already-used email returns HTTP 400."""
        self.client.post(self.url, self.valid_payload, format="json")
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_required_fields_returns_400(self) -> None:
        """Omitting required fields returns HTTP 400."""
        payloads = [
            {k: v for k, v in self.valid_payload.items() if k != field}
            for field in ("email", "password", "first_name", "last_name")
        ]
        for incomplete in payloads:
            with self.subTest(missing=set(self.valid_payload) - set(incomplete)):
                response = self.client.post(self.url, incomplete, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_not_returned_in_response(self) -> None:
        """The response body must never contain the password field."""
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data)


class LoginViewTests(APITestCase):
    """Test ``POST /api/v1/auth/login/``."""

    def setUp(self) -> None:
        self.url = reverse("accounts:login")
        self.email = "merchant@example.com"
        self.password = "secure-pass-123"

        from apps.accounts.services import RegistrationService

        RegistrationService.register_user(
            email=self.email,
            password=self.password,
            first_name="Jane",
            last_name="Doe",
        )

    def test_valid_credentials_return_200(self) -> None:
        """Login with valid credentials returns HTTP 200."""
        response = self.client.post(
            self.url,
            {"email": self.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_access_and_refresh_tokens(self) -> None:
        """A successful login returns both 'access' and 'refresh' tokens."""
        response = self.client.post(
            self.url,
            {"email": self.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIsInstance(response.data["access"], str)
        self.assertIsInstance(response.data["refresh"], str)

    def test_invalid_password_returns_400(self) -> None:
        """Login with a wrong password returns HTTP 400."""
        response = self.client.post(
            self.url,
            {"email": self.email, "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_email_returns_400(self) -> None:
        """Login with an unregistered email returns HTTP 400."""
        response = self.client.post(
            self.url,
            {"email": "unknown@example.com", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_disabled_user_returns_400(self) -> None:
        """Login for a disabled (is_active=False) user returns HTTP 400."""
        user = User.objects.get(email=self.email)
        user.is_active = False
        user.save()

        response = self.client.post(
            self.url,
            {"email": self.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
