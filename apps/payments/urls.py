"""URL configuration for the ``payments`` app."""

from django.urls import path

from apps.payments.views import PaymentDetailView, PaymentListCreateView

app_name = "payments"

urlpatterns = [
    path("payments/", PaymentListCreateView.as_view(), name="payment-list"),
    path(
        "payments/<uuid:pk>/",
        PaymentDetailView.as_view(),
        name="payment-detail",
    ),
]
