"""URL configuration for the ``products`` app."""

from django.urls import path

from apps.products.views import ProductDetailView, ProductListCreateView

app_name = "products"

urlpatterns = [
    path("products/", ProductListCreateView.as_view(), name="product-list"),
    path(
        "products/<uuid:pk>/",
        ProductDetailView.as_view(),
        name="product-detail",
    ),
]
