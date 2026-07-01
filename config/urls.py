"""
URL configuration for MerchantHub.

Defines the top-level URL routing for the project, including:

- Django admin (`/admin/`)
- API v1 endpoints (`/api/v1/`)
- OpenAPI schema (`/api/schema/`)
- Swagger UI (`/api/docs/`)
- Health check (`/health/`)
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def health_check(request):
    """Simple health check endpoint. Returns 200 when the server is running."""
    return JsonResponse({"status": "healthy", "database": "configured"})


urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # Health check
    path("health/", health_check, name="health-check"),
    # OpenAPI schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Swagger UI
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # API v1
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.workspaces.urls")),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.customers.urls")),
    path("api/v1/", include("apps.sales.urls")),
    path("api/v1/", include("apps.payments.urls")),
    path("api/v1/", include("apps.expenses.urls")),
    path("api/v1/", include("apps.dashboard.urls")),
]
