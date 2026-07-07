"""
Tests for the Foundation (Sprint 0) shared components.

Covers:
- ``apps.common.validators`` — validate_positive_decimal, etc.
- ``apps.common.exceptions`` — custom exceptions and exception handler
- ``apps.common.permissions`` — permission classes
- ``apps.common.pagination`` — DefaultPagination
- ``apps.common.middleware`` — WorkspaceMiddleware
- ``apps.common.models`` — Notification, AuditLog
"""

from decimal import Decimal
from unittest.mock import Mock

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpRequest
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIRequestFactory

from apps.common.exceptions import (
    DuplicateSkuError,
    InsufficientStockError,
    NotWorkspaceMemberError,
    OwnerCannotRemoveSelfError,
    PaymentExceedsTotalError,
    WorkspaceRequiredError,
    custom_exception_handler,
)
from apps.common.middleware import WorkspaceMiddleware
from apps.common.models import AuditLog, Notification
from apps.common.pagination import DefaultPagination
from apps.common.permissions import IsManagerOrAbove, IsWorkspaceMember, IsWorkspaceOwner
from apps.common.validators import (
    validate_iso_currency,
    validate_non_negative_decimal,
    validate_phone,
    validate_positive_decimal,
)


# ===========================================================================
# Validators
# ===========================================================================


class ValidatorTests(TestCase):
    """Tests for shared validators."""

    def test_validate_positive_decimal_passes(self):
        """A value > 0 should not raise."""
        try:
            validate_positive_decimal(Decimal("0.01"))
            validate_positive_decimal(Decimal("100"))
        except DjangoValidationError:
            self.fail("validate_positive_decimal raised unexpectedly")

    def test_validate_positive_decimal_fails_on_zero(self):
        """A value == 0 should raise."""
        with self.assertRaises(DjangoValidationError):
            validate_positive_decimal(Decimal("0"))

    def test_validate_positive_decimal_fails_on_negative(self):
        """A value < 0 should raise."""
        with self.assertRaises(DjangoValidationError):
            validate_positive_decimal(Decimal("-5"))

    def test_validate_positive_decimal_passes_on_none(self):
        """None should be skipped (optional field)."""
        try:
            validate_positive_decimal(None)
        except DjangoValidationError:
            self.fail("validate_positive_decimal raised on None")

    def test_validate_non_negative_decimal_passes(self):
        """Zero and positive values should pass."""
        try:
            validate_non_negative_decimal(Decimal("0"))
            validate_non_negative_decimal(Decimal("50"))
        except DjangoValidationError:
            self.fail("validate_non_negative_decimal raised unexpectedly")

    def test_validate_non_negative_decimal_fails_on_negative(self):
        """Negative values should raise."""
        with self.assertRaises(DjangoValidationError):
            validate_non_negative_decimal(Decimal("-1"))

    def test_validate_phone_passes_on_valid(self):
        """Valid phone formats should pass."""
        try:
            validate_phone("+1234567890")
            validate_phone("08001234567")
            validate_phone("+1 (555) 123-4567")
        except DjangoValidationError:
            self.fail("validate_phone raised on valid input")

    def test_validate_phone_fails_on_too_short(self):
        """Phone with fewer than 7 digits should raise."""
        with self.assertRaises(DjangoValidationError):
            validate_phone("12345")

    def test_validate_phone_passes_on_empty(self):
        """Empty string should be skipped."""
        try:
            validate_phone("")
        except DjangoValidationError:
            self.fail("validate_phone raised on empty string")

    def test_validate_iso_currency_passes(self):
        """Valid ISO 4217 codes should pass."""
        try:
            validate_iso_currency("USD")
            validate_iso_currency("EUR")
            validate_iso_currency("NGN")
        except DjangoValidationError:
            self.fail("validate_iso_currency raised on valid code")

    def test_validate_iso_currency_fails_on_wrong_length(self):
        """Codes not exactly 3 characters should raise."""
        with self.assertRaises(DjangoValidationError):
            validate_iso_currency("US")


# ===========================================================================
# Exceptions
# ===========================================================================


class ExceptionTests(TestCase):
    """Tests for custom domain exceptions."""

    def test_workspace_required_error(self):
        exc = WorkspaceRequiredError()
        self.assertEqual(exc.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(exc.default_code, "WORKSPACE_REQUIRED")

    def test_not_workspace_member_error(self):
        exc = NotWorkspaceMemberError()
        self.assertEqual(exc.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(exc.default_code, "NOT_WORKSPACE_MEMBER")

    def test_insufficient_stock_error_with_details(self):
        details = {"product_id": "abc", "available": 2, "requested": 5}
        exc = InsufficientStockError(details=details)
        self.assertEqual(exc.detail["code"], "INSUFFICIENT_STOCK")
        self.assertEqual(exc.detail["details"]["available"], 2)

    def test_insufficient_stock_error_without_details(self):
        exc = InsufficientStockError()
        self.assertEqual(exc.detail["details"], {})

    def test_payment_exceeds_total_error(self):
        details = {"sale_total": 100, "current_paid": 80, "attempted": 50}
        exc = PaymentExceedsTotalError(details=details)
        self.assertEqual(exc.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(exc.detail["code"], "PAYMENT_EXCEEDS_TOTAL")
        self.assertEqual(exc.detail["details"]["attempted"], 50)

    def test_owner_cannot_remove_self_error(self):
        exc = OwnerCannotRemoveSelfError()
        self.assertEqual(exc.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(exc.default_code, "OWNER_CANNOT_REMOVE_SELF")

    def test_duplicate_sku_error(self):
        exc = DuplicateSkuError(sku="ABC-123")
        self.assertEqual(exc.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("ABC-123", exc.detail["error"])
        self.assertEqual(exc.detail["details"]["sku"], "ABC-123")


class ExceptionHandlerTests(TestCase):
    """Tests for the custom DRF exception handler."""

    def test_handles_drf_validation_error_field_level(self):
        """Field-level validation errors should produce ``VALIDATION_ERROR`` with field details."""
        exc = DRFValidationError({"name": ["This field is required."]})
        response = custom_exception_handler(exc, None)
        self.assertIsNotNone(response)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertIn("name", response.data["details"])

    def test_handles_drf_validation_error_string(self):
        """String validation errors should produce a proper response."""
        exc = DRFValidationError("Some error.")
        response = custom_exception_handler(exc, None)
        self.assertIsNotNone(response)
        self.assertIn("error", response.data)

    def test_returns_none_for_unhandled_exceptions(self):
        """Unhandled exceptions should return None (fall through to 500)."""

        class UnknownError(Exception):
            pass

        response = custom_exception_handler(UnknownError("test"), None)
        self.assertIsNone(response)


# ===========================================================================
# Permissions
# ===========================================================================


class PermissionClassTests(TestCase):
    """Tests for custom permission classes."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = Mock()

    def _make_request(self, user=None, workspace=None):
        request = self.factory.get("/")
        request.user = user
        request.workspace = workspace
        return request

    def test_is_workspace_member_fails_without_user(self):
        request = self._make_request(user=None, workspace=Mock())
        perm = IsWorkspaceMember()
        self.assertFalse(perm.has_permission(request, self.view))

    def test_is_workspace_member_fails_without_workspace(self):
        user = Mock(is_authenticated=True)
        request = self._make_request(user=user, workspace=None)
        perm = IsWorkspaceMember()
        self.assertFalse(perm.has_permission(request, self.view))

    def test_is_workspace_owner_fails_without_workspace(self):
        user = Mock(is_authenticated=True)
        request = self._make_request(user=user, workspace=None)
        perm = IsWorkspaceOwner()
        self.assertFalse(perm.has_permission(request, self.view))

    def test_is_manager_or_above_fails_without_membership(self):
        user = Mock(is_authenticated=True, workspacemembership_set=Mock(filter=Mock(first=Mock(return_value=None))))
        workspace = Mock()
        request = self._make_request(user=user, workspace=workspace)
        perm = IsManagerOrAbove()
        self.assertFalse(perm.has_permission(request, self.view))


# ===========================================================================
# Pagination
# ===========================================================================


class PaginationTests(TestCase):
    """Tests for the default pagination class."""

    def test_default_page_size(self):
        paginator = DefaultPagination()
        self.assertEqual(paginator.page_size, 25)
        self.assertEqual(paginator.page_size_query_param, "page_size")
        self.assertEqual(paginator.max_page_size, 100)


# ===========================================================================
# Middleware
# ===========================================================================


class MiddlewareTests(TestCase):
    """Tests for ``WorkspaceMiddleware``."""

    def test_middleware_sets_none_when_no_header(self):
        request = HttpRequest()
        request.META = {}
        request.user = Mock(is_authenticated=False)
        mw = WorkspaceMiddleware(lambda req: None)
        mw.process_request(request)
        self.assertIsNone(getattr(request, "workspace", None))


# ===========================================================================
# Notification & AuditLog Models
# ===========================================================================


class NotificationModelTests(TestCase):
    """Tests for the ``Notification`` model."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            username="notif_test",
            email="notif@example.com",
            password="testpass123",
        )

    def test_create_notification(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.SALE_COMPLETED,
            title="Sale Completed",
            message="A sale of $50 was completed.",
        )
        self.assertIsNotNone(notif.pk)
        self.assertFalse(notif.is_read)
        self.assertIsNone(notif.read_at)
        self.assertEqual(str(notif), "[sale_completed] Sale Completed")

    def test_notification_defaults(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.LOW_STOCK_ALERT,
            title="Low Stock",
            message="Product XYZ is low on stock.",
        )
        self.assertFalse(notif.is_read)
        self.assertIsNone(notif.read_at)
        self.assertIsNone(notif.expires_at)


class AuditLogModelTests(TestCase):
    """Tests for the ``AuditLog`` model."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            username="audit_test",
            email="audit@example.com",
            password="testpass123",
        )

    def test_create_audit_log(self):
        log = AuditLog.objects.create(
            actor=self.user,
            action="entity.create.product",
            target_type="product",
            target_id=None,
            changes={"before": None, "after": {"name": "Test Product"}},
        )
        self.assertIsNotNone(log.pk)
        self.assertEqual(log.action, "entity.create.product")
        self.assertEqual(log.changes["after"]["name"], "Test Product")

    def test_audit_log_prevents_update(self):
        log = AuditLog.objects.create(
            actor=self.user,
            action="entity.create.product",
        )
        with self.assertRaises(RuntimeError):
            log.save()

    def test_audit_log_prevents_delete(self):
        log = AuditLog.objects.create(
            actor=self.user,
            action="entity.create.product",
        )
        with self.assertRaises(RuntimeError):
            log.delete()


# ===========================================================================
# WorkspaceModelStub Tests
# ===========================================================================


class WorkspaceStubTests(TestCase):
    """Tests for the minimal Workspace stub model."""

    def test_create_workspace(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        owner = User.objects.create_user(
            username="ws_stub",
            email="ws_stub@example.com",
            password="testpass123",
        )
        from apps.workspaces.models import Workspace

        ws = Workspace.objects.create(name="Stub WS", owner=owner)
        self.assertIsNotNone(ws.pk)
        self.assertEqual(str(ws), "Stub WS")
        self.assertEqual(ws.owner, owner)
