"""
Tests for the Dashboard API.

Covers both the DashboardService and the DashboardView endpoint.
"""

from __future__ import annotations

from decimal import Decimal

from django.urls import reverse
from django.utils import timezone as tz

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.dashboard.services import DashboardService
from apps.inventory.models import Inventory
from apps.payments.models import Payment
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem
from apps.sales.services import SalesService
from apps.workspaces.models import Workspace, WorkspaceMembership


class DashboardServiceTests(APITestCase):
    """Verify DashboardService aggregation logic."""

    def setUp(self) -> None:
        """Create workspace, user, product, inventory, and sales."""
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

        self.product = Product.objects.create(
            workspace=self.workspace,
            name="Test Product",
            sku="TST-001",
            cost_price="5.00",
            selling_price="12.99",
        )
        Inventory.objects.create(product=self.product, quantity=100)

        self.other_product = Product.objects.create(
            workspace=self.workspace,
            name="Other Product",
            sku="OTH-001",
            cost_price="3.00",
            selling_price="8.50",
        )
        Inventory.objects.create(product=self.other_product, quantity=50)

    def _create_sale(self, total: str = "25.98") -> Sale:
        """Helper to create a sale."""
        return SalesService.create_sale(
            workspace=self.workspace,
            created_by=self.user,
            items=[
                {"product": self.product, "quantity": 2},
            ],
        )

    def _create_payment(
        self,
        sale: Sale,
        status: str = "SUCCESS",
        amount: str | None = None,
    ) -> Payment:
        """Helper to create a payment."""
        return Payment.objects.create(
            workspace=self.workspace,
            sale=sale,
            amount=Decimal(amount or sale.total),
            payment_method=Payment.PaymentMethod.TRANSFER,
            status=status,
            provider_reference=f"ref-{sale.pk}",
        )

    # ------------------------------------------------------------------
    # Today's summary
    # ------------------------------------------------------------------

    def test_today_summary_returns_zero_when_no_data(self) -> None:
        """With no sales, today's summary shows zeros."""
        data = DashboardService._today_summary(workspace=self.workspace)
        self.assertEqual(data["sales_count"], 0)
        self.assertEqual(data["revenue"], "0.00")
        self.assertEqual(data["payments_count"], 0)

    def test_today_summary_counts_todays_sales(self) -> None:
        """Today's sales are counted correctly."""
        sale = self._create_sale()
        data = DashboardService._today_summary(workspace=self.workspace)
        self.assertEqual(data["sales_count"], 1)
        self.assertGreater(Decimal(data["revenue"]), 0)

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    def test_overview_returns_zero_when_no_data(self) -> None:
        """With no data, overview shows zeros."""
        data = DashboardService._overview(workspace=self.workspace)
        self.assertEqual(data["total_sales"], 0)
        self.assertEqual(data["total_revenue"], "0.00")
        self.assertEqual(data["total_payments"], 0)
        self.assertEqual(data["total_products"], 2)
        self.assertEqual(data["total_customers"], 0)

    def test_overview_counts_paid_vs_pending_sales(self) -> None:
        """Paid vs pending sales are counted correctly."""
        sale1 = self._create_sale()
        sale2 = self._create_sale()

        self._create_payment(sale1, status="SUCCESS")
        sale1.payment_status = Sale.PaymentStatus.PAID
        sale1.save()

        data = DashboardService._overview(workspace=self.workspace)
        self.assertEqual(data["paid_sales"], 1)
        self.assertEqual(data["pending_sales"], 1)

    def test_overview_pending_payments_sum(self) -> None:
        """Pending payments sum is calculated correctly."""
        sale = self._create_sale()
        self._create_payment(sale, status="PENDING", amount="25.98")

        data = DashboardService._overview(workspace=self.workspace)
        self.assertEqual(data["pending_payments"], 1)
        self.assertGreater(Decimal(data["pending_payments_sum"]), 0)

    # ------------------------------------------------------------------
    # Payment breakdown
    # ------------------------------------------------------------------

    def test_payment_breakdown_groups_by_status(self) -> None:
        """Payment breakdown returns counts grouped by status."""
        sale1 = self._create_sale()
        sale2 = self._create_sale()

        self._create_payment(sale1, status="SUCCESS")
        self._create_payment(sale2, status="PENDING")

        data = DashboardService._payment_breakdown(
            workspace=self.workspace,
        )
        statuses = {item["status"]: item["count"] for item in data}
        self.assertEqual(statuses.get("SUCCESS"), 1)
        self.assertEqual(statuses.get("PENDING"), 1)

    # ------------------------------------------------------------------
    # Recent sales
    # ------------------------------------------------------------------

    def test_recent_sales_returns_limit(self) -> None:
        """Recent sales returns at most the specified limit."""
        for _ in range(15):
            self._create_sale()

        data = DashboardService._recent_sales(
            workspace=self.workspace,
            limit=10,
        )
        self.assertLessEqual(len(data), 10)

    def test_recent_sales_includes_payment_info(self) -> None:
        """Recent sales include payment status detail."""
        sale = self._create_sale()
        payment = self._create_payment(sale, status="SUCCESS")

        data = DashboardService._recent_sales(
            workspace=self.workspace,
            limit=10,
        )
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["payment_status_detail"], "SUCCESS")
        self.assertEqual(data[0]["payment_id"], str(payment.pk))

    # ------------------------------------------------------------------
    # Low stock
    # ------------------------------------------------------------------

    def test_low_stock_returns_products_below_threshold(self) -> None:
        """Products with quantity < threshold are returned."""
        Inventory.objects.filter(product=self.product).update(quantity=3)

        data = DashboardService._low_stock(
            workspace=self.workspace,
            threshold=10,
        )
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["sku"], "TST-001")
        self.assertEqual(data[0]["quantity"], 3)

    def test_low_stock_excludes_products_above_threshold(self) -> None:
        """Products with quantity >= threshold are excluded."""
        data = DashboardService._low_stock(
            workspace=self.workspace,
            threshold=10,
        )
        self.assertEqual(len(data), 0)


class DashboardAPIViewTests(APITestCase):
    """Test the Dashboard API endpoint."""

    def setUp(self) -> None:
        """Create user, workspace, and authenticate."""
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
        self._authenticate(self.user)
        self.dashboard_url = reverse("dashboard:dashboard")
        self.summary_url = reverse("dashboard:dashboard-summary")

    def _authenticate(self, user: User) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def test_unauthenticated_returns_401(self) -> None:
        """GET /dashboard/ without auth returns 401."""
        self.client.credentials()
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ------------------------------------------------------------------
    # Dashboard response structure
    # ------------------------------------------------------------------

    def test_dashboard_returns_expected_sections(self) -> None:
        """The dashboard response contains all expected sections."""
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_sections = [
            "today",
            "overview",
            "payment_breakdown",
            "recent_sales",
            "low_stock",
            "top_products",
            "revenue_trend",
        ]
        for section in expected_sections:
            self.assertIn(section, response.data)

    def test_dashboard_today_has_expected_fields(self) -> None:
        """The 'today' section has all expected fields."""
        response = self.client.get(self.dashboard_url)
        today = response.data["today"]
        for field in ["sales_count", "revenue", "payments_count", "payments_sum", "date"]:
            self.assertIn(field, today)

    def test_dashboard_overview_has_expected_fields(self) -> None:
        """The 'overview' section has all expected fields."""
        response = self.client.get(self.dashboard_url)
        overview = response.data["overview"]
        for field in [
            "total_sales",
            "total_revenue",
            "average_sale_value",
            "paid_sales",
            "pending_sales",
            "total_products",
            "total_customers",
        ]:
            self.assertIn(field, overview)

    # ------------------------------------------------------------------
    # Summary response
    # ------------------------------------------------------------------

    def test_summary_returns_lightweight_data(self) -> None:
        """The summary endpoint returns lightweight metrics."""
        response = self.client.get(self.summary_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_fields = [
            "today_revenue",
            "today_sales_count",
            "total_sales",
            "total_revenue",
            "paid_sales",
            "pending_sales",
            "pending_payments_count",
            "low_stock_count",
            "total_customers",
            "total_products",
        ]
        for field in expected_fields:
            self.assertIn(field, response.data)

    # ------------------------------------------------------------------
    # Workspace isolation
    # ------------------------------------------------------------------

    def test_dashboard_is_scoped_to_workspace(self) -> None:
        """Dashboard data is scoped to the authenticated workspace."""
        # Create data in another workspace
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
        )
        other_workspace = Workspace.objects.create(
            owner=other_user,
            name="Other Store",
            slug="other-store",
        )
        WorkspaceMembership.objects.create(
            user=other_user,
            workspace=other_workspace,
            role=WorkspaceMembership.Role.OWNER,
        )
        other_product = Product.objects.create(
            workspace=other_workspace,
            name="Other Product",
            sku="OTH-001",
            cost_price="5.00",
            selling_price="20.00",
        )
        Inventory.objects.create(product=other_product, quantity=10)

        # Our workspace should have 0 sales
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.data["overview"]["total_sales"], 0)
        self.assertEqual(response.data["overview"]["total_products"], 0)
