from django.contrib import admin

from apps.payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "workspace",
        "sale",
        "amount",
        "currency",
        "payment_method",
        "status",
        "created_at",
    ]
    list_filter = ["status", "payment_method", "workspace"]
    search_fields = [
        "provider_reference",
        "external_reference",
    ]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
    ]
