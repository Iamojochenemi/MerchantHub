from django.contrib import admin

from apps.products.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "workspace", "selling_price", "is_active"]
    list_filter = ["is_active", "workspace"]
    search_fields = ["name", "sku"]
