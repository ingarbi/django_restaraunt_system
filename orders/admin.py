from datetime import date

from admin_totals.admin import ModelAdminTotals
from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.db.models import Avg, F, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Category, MenuItem, Order, OrderItem

admin.site.register(Category)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(ModelAdminTotals):
    list_display = (

        "order_number",
        "status",
        "created_at",
        "order_type",
        "discount",
        "total_sum",
        "payment_type",
        'created_by',
    )
    readonly_fields = ('created_by',  "completion_time",)
    list_totals = [
        ("total_sum", lambda field: Coalesce(Sum(field), 0)),
    ]
    inlines = [OrderItemInline]
    list_display_links = [
        "order_number",
    ]
    search_fields = ["order_number"]
    list_filter = ["status", "order_type", "created_at", 'created_by', "payment_type"]

    def completion_time(self, obj):
        """Время выполнения заказа"""
        if obj.completed_at and obj.created_at:
            # Рассчитываем разницу во времени
            time_diff = obj.completed_at - obj.created_at
            total_seconds = time_diff.total_seconds()
            
            # Форматируем в читаемый вид
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            
            if hours > 0:
                return f"{hours} ч {minutes} м"
            else:
                return f"{minutes} м"
        return "Не завершен"
    
    completion_time.short_description = "Время приготовления"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "menu_item",
        "quantity",
        "order_link",
        "created_date",
        "completion_time",
        "sales_report_link",
    )
    list_filter = (
        ("order__created_at", DateFieldListFilter),
        ("order__completed_at", DateFieldListFilter),
        "menu_item",
    )

    def completion_time(self, obj):
        """Время выполнения заказа"""
        if obj.order.completed_at and obj.order.created_at:
            time_diff = obj.order.completed_at - obj.order.created_at
            total_seconds = time_diff.total_seconds()
            
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            
            if hours > 0:
                return f"{hours} ч {minutes} м"
            else:
                return f"{minutes} м"
        return "Не завершен"
    
    completion_time.short_description = "Время приготовления"
    completion_time.admin_order_field = "order__completed_at"

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)

        if request.method == "GET" and "date" in request.GET:
            selected_date = request.GET["date"]
            return self.sales_by_date(request, selected_date)

        return response

    def sales_by_date(self, request, selected_date):
        # Parse date from string (format: YYYY-MM-DD)
        try:
            filter_date = date.fromisoformat(selected_date)
        except ValueError:
            filter_date = date.today()

        # Get aggregated sales data
        sales_data = (
            OrderItem.objects.filter(
                order__created_at__date=filter_date, order__status="delivered"
            )
            .values("menu_item__name")
            .annotate(
                total_quantity=Sum("quantity"),
                total_revenue=Sum(F("quantity") * F("menu_item__price")),
            )
            .order_by("-total_quantity")
        )

        context = {
            **self.admin_site.each_context(request),
            "sales_data": sales_data,
            "selected_date": filter_date,
            "title": f"Sales Report for {filter_date.strftime('%Y-%m-%d')}",
        }

        return render(request, "admin/sales_report.html", context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sales-report/",
                self.admin_site.admin_view(self.sales_report_view),
                name="sales_report",
            ),
        ]
        return custom_urls + urls

    def sales_report_view(self, request):
        # Default to today's date
        default_date = date.today().isoformat()
        return self.sales_by_date(request, request.GET.get("date", default_date))

    def order_link(self, obj):
        return format_html(
            '<a href="{}">#{}</a>',
            reverse("admin:orders_order_change", args=[obj.order.id]),
            obj.order.order_number[-3:],
        )

    def created_date(self, obj):
        return obj.order.created_at.date()

    def sales_report_link(self, obj):
        return format_html(
            '<a href="/admin/orders/orderitem/sales-report/">#Репорт</a>',
        )

    created_date.admin_order_field = "order__created_at"
    order_link.short_description = "Заказ"
    created_date.short_description = "Дата"
    sales_report_link.short_description = "Отчеты"


class CustomAdminSite(admin.AdminSite):
    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["sales_report_url"] = reverse("admin:sales_report")
        return super().index(request, extra_context)


admin_site = CustomAdminSite(name="myadmin")

admin.site.site_header = "Панель администратора"
admin.site.site_title = "Панель администратора"
admin.site.index_title = ""
