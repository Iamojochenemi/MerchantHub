from django.contrib import admin

from apps.customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        "first_name",
        "last_name",
        "phone_number",
        "email",
        "workspace",
    ]
    list_filter = ["workspace"]
    search_fields = ["first_name", "last_name", "phone_number", "email"]
