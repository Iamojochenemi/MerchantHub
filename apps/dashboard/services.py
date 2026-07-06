"""
Dashboard service for MerchantHub.

Aggregates data from Sales, Payments, Products, Inventory, Customers,
and StockMovements to produce a comprehensive business overview for
both petty traders and big traders.

All methods accept a ``workspace`` to enforce multi-tenant isolation.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone as tz

from apps.payments.models import Payment
from apps.sales.models import Sale, SaleItem
from apps.inventory.models import Inventory
from apps.products.models import Product
from apps.customers.models import Customer


def _fmt(value: Decimal | None) -> str:
    """Format a decimal value consistently as 'X.XX'."""
    return f"{Decimal(str(value or 0)):.2f}"


class DashboardService:
    """Aggregate business metrics for a workspace.

    Usage::

        from apps.dashboard.services import DashboardService

        data = DashboardService.get_full_dashboard(workspace=my_workspace)
        print(data["overview"])
    """

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    @staticmethod
    def get_full_dashboard(
        *,
        workspace,
        days: int = 30,
    ) -> dict[str, Any]:
        """Return all dashboard metrics for the given workspace.

        .. note::

            This method runs **7 queries** and should be used for the
            full dashboard view only. For the nav bar / header, use
            :meth:`get_summary` which runs a leaner query set.

        Parameters
        ----------
        workspace:
            The ``Workspace`` instance to scope data to.
        days:
            Number of days to look back for trends (default: 30).

        Returns
        -------
        dict[str, Any]
            A dictionary with the following sections:

            - ``today`` — today's sales, revenue, payments
            - ``overview`` — totals for sales, revenue, payments, customers, products
            - ``payment_breakdown`` — count of payments by status
            - ``recent_sales`` — last 10 sales with payment info
            - ``low_stock`` — products with quantity below threshold
            - ``top_products`` — top 10 products by units sold
            - ``revenue_trend`` — daily revenue for the last ``days``
        """
        return {
            "today": DashboardService._today_summary(workspace=workspace),
            "overview": DashboardService._overview(workspace=workspace),
            "payment_breakdown": DashboardService._payment_breakdown(
                workspace=workspace,
            ),
            "recent_sales": DashboardService._recent_sales(
                workspace=workspace,
            ),
            "low_stock": DashboardService._low_stock(
                workspace=workspace,
            ),
            "top_products": DashboardService._top_products(
                workspace=workspace,
                days=days,
            ),
            "revenue_trend": DashboardService._revenue_trend(
                workspace=workspace,
                days=days,
            ),
        }

    # ------------------------------------------------------------------
    # Lightweight summary (for nav bar / header)
    # ------------------------------------------------------------------

    @staticmethod
    def get_summary(
        *,
        workspace,
    ) -> dict[str, Any]:
        """Return lightweight metrics for the dashboard header.

        Runs only 3 simple queries (vs 7 for the full dashboard).

        Parameters
        ----------
        workspace:
            The ``Workspace`` instance to scope data to.

n        Returns
        -------
        dict[str, Any]
            Lightweight summary with 10 fields.
        """
        today_start = tz.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        sales_today = Sale.objects.filter(
            workspace=workspace,
            created_at__gte=today_start,
        )
        payments_pending = Payment.objects.filter(
            workspace=workspace,
            status=Payment.Status.PENDING,
        )
        low_stock_count = Inventory.objects.filter(
            product__workspace=workspace,
            quantity__lt=10,
        ).count()

        return {
            "today_revenue": _fmt(
                sales_today.aggregate(
                    total=Sum("total", default=Decimal("0.00")),
                )["total"]
            ),
            "today_sales_count": sales_today.count(),
            "total_sales": Sale.objects.filter(workspace=workspace).count(),
            "total_revenue": _fmt(
                Sale.objects.filter(workspace=workspace).aggregate(
                    total=Sum("total", default=Decimal("0.00")),
                )["total"]
            ),
            "paid_sales": Sale.objects.filter(
                workspace=workspace,
                payment_status=Sale.PaymentStatus.PAID,
            ).count(),
            "pending_sales": Sale.objects.filter(
                workspace=workspace,
                payment_status=Sale.PaymentStatus.PENDING_PAYMENT,
            ).count(),
            "pending_payments_count": payments_pending.count(),
            "low_stock_count": low_stock_count,
            "total_customers": Customer.objects.filter(
                workspace=workspace,
            ).count(),
            "total_products": Product.objects.filter(
                workspace=workspace,
            ).count(),
        }

    # ------------------------------------------------------------------
    # Today's summary
    # ------------------------------------------------------------------

    @staticmethod
    def _today_summary(*, workspace) -> dict[str, Any]:
        """Return key metrics for today only."""
        today_start = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)

        sales_today = Sale.objects.filter(
            workspace=workspace,
            created_at__gte=today_start,
        )
        payments_today = Payment.objects.filter(
            workspace=workspace,
            created_at__gte=today_start,
        )

        today_revenue = sales_today.aggregate(
            total=Sum("total", default=Decimal("0.00")),
        )["total"]

        today_payments_sum = payments_today.aggregate(
            total=Sum("amount", default=Decimal("0.00")),
        )["total"]

        return {
            "sales_count": sales_today.count(),
            "revenue": _fmt(today_revenue),
            "payments_count": payments_today.count(),
            "payments_sum": _fmt(today_payments_sum),
            "date": str(tz.now().date()),
        }

    # ------------------------------------------------------------------
    # Overview (all-time / broad metrics)
    # ------------------------------------------------------------------

    @staticmethod
    def _overview(*, workspace) -> dict[str, Any]:
        """Return high-level business metrics."""
        sales = Sale.objects.filter(workspace=workspace)
        payments = Payment.objects.filter(workspace=workspace)

        total_revenue = sales.aggregate(
            total=Sum("total", default=Decimal("0.00")),
        )["total"]

        total_payments = payments.aggregate(
            total=Sum("amount", default=Decimal("0.00")),
        )["total"]

        pending_payments = payments.filter(
            status=Payment.Status.PENDING,
        )

        pending_sum = pending_payments.aggregate(
            total=Sum("amount", default=Decimal("0.00")),
        )["total"]

        total_products = Product.objects.filter(workspace=workspace).count()
        total_customers = Customer.objects.filter(workspace=workspace).count()

        # Paid vs unpaid sales
        paid_sales = sales.filter(
            payment_status=Sale.PaymentStatus.PAID,
        ).count()
        pending_sales = sales.filter(
            payment_status=Sale.PaymentStatus.PENDING_PAYMENT,
        ).count()

        return {
            "total_sales": sales.count(),
            "total_revenue": _fmt(total_revenue),
            "average_sale_value": _fmt(
                total_revenue / sales.count()
                if sales.count() > 0
                else Decimal("0.00")
            ),
            "total_payments": payments.count(),
            "total_payments_sum": _fmt(total_payments),
            "pending_payments": pending_payments.count(),
            "pending_payments_sum": _fmt(pending_sum),
            "paid_sales": paid_sales,
            "pending_sales": pending_sales,
            "total_products": total_products,
            "total_customers": total_customers,
        }

    # ------------------------------------------------------------------
    # Payment breakdown by status
    # ------------------------------------------------------------------

    @staticmethod
    def _payment_breakdown(*, workspace) -> list[dict[str, Any]]:
        """Return payment counts grouped by status."""
        qs = (
            Payment.objects
            .filter(workspace=workspace)
            .values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )
        return [
            {
                "status": item["status"],
                "count": item["count"],
            }
            for item in qs
        ]

    # ------------------------------------------------------------------
    # Recent sales
    # ------------------------------------------------------------------

    @staticmethod
    def _recent_sales(*, workspace, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most recent sales with payment information."""
        recent = (
            Sale.objects
            .filter(workspace=workspace)
            .select_related("created_by")
            .prefetch_related("payments")
            .order_by("-created_at")[:limit]
        )

        result = []
        for sale in recent:
            # Get the latest payment for this sale
            latest_payment = sale.payments.order_by("-created_at").first()
            result.append(
                {
                    "id": str(sale.pk),
                    "total": str(sale.total),
                    "payment_status": sale.payment_status,
                    "payment_status_label": (
                        Sale.PaymentStatus(sale.payment_status).label
                    ),
                    "created_at": sale.created_at.isoformat(),
                    "created_by": (
                        f"{sale.created_by.first_name} "
                        f"{sale.created_by.last_name}"
                    ).strip(),
                    "payment_status_detail": (
                        latest_payment.status
                        if latest_payment
                        else "NO_PAYMENT"
                    ),
                    "payment_id": (
                        str(latest_payment.pk)
                        if latest_payment
                        else None
                    ),
                }
            )
        return result

    # ------------------------------------------------------------------
    # Low stock alerts
    # ------------------------------------------------------------------

    @staticmethod
    def _low_stock(*, workspace, threshold: int = 10) -> list[dict[str, Any]]:
        """Return products with inventory below the threshold."""
        low = (
            Inventory.objects
            .filter(product__workspace=workspace, quantity__lt=threshold)
            .select_related("product")
            .order_by("quantity")
        )

        return [
            {
                "product_id": str(item.product.pk),
                "product_name": item.product.name,
                "sku": item.product.sku,
                "quantity": item.quantity,
            }
            for item in low
        ]

    # ------------------------------------------------------------------
    # Top products by units sold
    # ------------------------------------------------------------------

    @staticmethod
    def _top_products(
        *,
        workspace,
        days: int = 30,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return top N products by quantity sold in the last ``days``."""
        from django.db.models import F

        since = tz.now() - timedelta(days=days)

        top = (
            SaleItem.objects
            .filter(
                sale__workspace=workspace,
                sale__created_at__gte=since,
            )
            .values(
                product_name=F("product__name"),
                product_sku=F("product__sku"),
            )
            .annotate(
                total_quantity=Sum("quantity"),
                total_revenue=Sum("line_total"),
            )
            .order_by("-total_quantity")[:limit]
        )

        return [
            {
                "product_name": item["product_name"],
                "sku": item["product_sku"],
                "units_sold": item["total_quantity"],
                "revenue": _fmt(item["total_revenue"]),
            }
            for item in top
        ]

    # ------------------------------------------------------------------
    # Revenue trend (daily)
    # ------------------------------------------------------------------

    @staticmethod
    def _revenue_trend(
        *,
        workspace,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Return daily revenue for the last ``days``."""
        since = tz.now() - timedelta(days=days)

        daily = (
            Sale.objects
            .filter(workspace=workspace, created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(
                revenue=Sum("total", output_field=DecimalField()),
                sales_count=Count("id"),
            )
            .order_by("date")
        )

        return [
            {
                "date": str(item["date"]),
                "revenue": _fmt(item["revenue"]),
                "sales_count": item["sales_count"],
            }
            for item in daily
        ]
