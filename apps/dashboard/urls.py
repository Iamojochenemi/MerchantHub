"""
URL configuration for the dashboard app.
"""

from django.urls import path

from apps.dashboard.views import DashboardSummaryView, DashboardView

app_name = "dashboard"

urlpatterns = [
    path(
        "dashboard/",
        DashboardView.as_view(),
        name="dashboard",
    ),
    path(
        "dashboard/summary/",
        DashboardSummaryView.as_view(),
        name="dashboard-summary",
    ),
]
