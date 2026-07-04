from django.contrib import admin

from apps.sales.models import Sale, SaleItem


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ["id", "workspace", "created_by", "total", "created_at"]
    list_filter = ["workspace"]
    search_fields = ["created_by__email"]
    date_hierarchy = "created_at"


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ["sale", "product", "quantity", "unit_price", "line_total"]
    search_fields = ["product__name", "product__sku"]
