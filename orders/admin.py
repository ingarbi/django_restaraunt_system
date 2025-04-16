from django.contrib import admin
from .models import Order, OrderItem, MenuItem, Category


admin.site.register(OrderItem)
admin.site.register(Category)



class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'order_number', 'created_at', 'order_type', "total_sum" )
    inlines = [OrderItemInline]

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'price')