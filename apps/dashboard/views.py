"""
Dashboard API views for MerchantHub.

Provides a single endpoint that returns all aggregated business
metrics for the authenticated user's workspace.
"""

from __future__ import annotations

from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.dashboard.services import DashboardService
from apps.workspaces.utils import get_active_workspace


class DashboardView(generics.GenericAPIView):
    """Return aggregated business metrics for the authenticated merchant.

    **GET** ``/dashboard/`` — Returns a comprehensive business overview
    including today's summary, all-time metrics, payment breakdown,
    recent sales, low stock alerts, top products, and revenue trends.

    All data is scoped to the authenticated user's active workspace.

    **Response sections:**

    - ``today`` — Today's sales count, revenue, payments count, payments sum
    - ``overview`` — Total sales, total revenue, average sale, paid/pending sales
    - ``payment_breakdown`` — Count of payments grouped by status
    - ``recent_sales`` — Last 10 sales with payment status detail
    - ``low_stock`` — Products with quantity below 10
    - ``top_products`` — Top 10 products by units sold (last 30 days)
    - ``revenue_trend`` — Daily revenue for the last 30 days
    """

    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def get(self, request):
        """Return the full dashboard data."""
        workspace = get_active_workspace(request)

        data = DashboardService.get_full_dashboard(workspace=workspace)

        return Response(data, status=status.HTTP_200_OK)


class DashboardSummaryView(generics.GenericAPIView):
    """Return a lightweight dashboard summary for quick views.

    **GET** ``/dashboard/summary/`` — Returns only the high-level
    metrics: today's revenue, total sales, paid sales, pending
    payments, low stock count, and total customers.

    Designed for the nav bar / header of the frontend.
    """

    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def get(self, request):
        """Return the lightweight summary."""
        workspace = get_active_workspace(request)

        summary = DashboardService.get_summary(workspace=workspace)

        return Response(summary, status=status.HTTP_200_OK)
