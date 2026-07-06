from django.contrib import admin

from apps.stock_movements.models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        "inventory",
        "movement_type",
        "quantity",
        "quantity_before",
        "quantity_after",
        "reference",
        "created_by",
        "created_at",
    ]
    list_filter = ["movement_type"]
    search_fields = [
        "reference",
        "inventory__product__name",
        "inventory__product__sku",
    ]
    readonly_fields = [
        "inventory",
        "movement_type",
        "quantity",
        "quantity_before",
        "quantity_after",
        "reference",
        "created_by",
        "created_at",
    ]
