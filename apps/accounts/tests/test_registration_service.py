"""Tests for ``RegistrationService.register_user``."""

from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.services import RegistrationService
from apps.workspaces.models import BusinessProfile, Workspace, WorkspaceMembership


class RegistrationServiceTests(TestCase):
    """Verify that ``register_user`` creates the full object graph."""

    def setUp(self) -> None:
        self.email = "merchant@example.com"
        self.password = "secure-pass-123"
        self.first_name = "Jane"
        self.last_name = "Doe"

        self.user = RegistrationService.register_user(
            email=self.email,
            password=self.password,
            first_name=self.first_name,
            last_name=self.last_name,
        )

        self.workspace = self.user.owned_workspaces.get()
        self.profile = self.workspace.business_profile
        self.membership = self.workspace.memberships.get()

    def test_user_created(self) -> None:
        """A single ``User`` record must exist after registration."""
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(self.user.email, self.email)
        self.assertTrue(self.user.check_password(self.password))

    def test_workspace_created(self) -> None:
        """A single ``Workspace`` must exist and be owned by the user."""
        self.assertEqual(Workspace.objects.count(), 1)
        self.assertEqual(self.workspace.owner, self.user)

    def test_business_profile_created(self) -> None:
        """A single ``BusinessProfile`` must exist and belong to the workspace."""
        self.assertEqual(BusinessProfile.objects.count(), 1)
        self.assertEqual(self.profile.workspace, self.workspace)

    def test_workspace_membership_created(self) -> None:
        """A single ``WorkspaceMembership`` must exist with OWNER role."""
        self.assertEqual(WorkspaceMembership.objects.count(), 1)
        self.assertEqual(self.membership.user, self.user)
        self.assertEqual(self.membership.workspace, self.workspace)
        self.assertEqual(self.membership.role, WorkspaceMembership.Role.OWNER)

    def test_all_relationships_are_correct(self) -> None:
        """Cross-verify that user owns exactly one workspace with a profile
        and an owner membership."""
        self.assertEqual(self.user.owned_workspaces.count(), 1)
        self.assertEqual(self.user.owned_workspaces.get(), self.workspace)
        self.assertEqual(self.workspace.business_profile.workspace, self.workspace)
        self.assertEqual(
            self.workspace.memberships.get().role,
            WorkspaceMembership.Role.OWNER,
        )
