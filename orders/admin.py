from django.contrib import admin
from .models import Order, OrderItem, MenuItem, Category



admin.site.register(Category)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_number",
        "status",
        "created_at",
        "order_type",
        "total_sum",
        "payment_type",
    )
    inlines = [OrderItemInline]
    list_display_links = [
        "id",
        "order_number",
    ]
    search_fields = ["order_number"]
    list_filter = ["status", "order_type","created_at"]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price")

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("menu_item","order","quantity", )
