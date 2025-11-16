from django.utils import timezone
from datetime import date, datetime, timedelta

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


class DateTimeFilter(admin.SimpleListFilter):
    title = 'Дата и время создания'
    parameter_name = 'created_at'

    def lookups(self, request, model_admin):
        lookups_list = [
            ('today', 'Сегодня'),
            ('yesterday', 'Вчера'),
            ('this_week', 'Эта неделя'),
            ('this_month', 'Этот месяц'),
            ('last_24_hours', 'Последние 24 часа'),
            ('last_7_days', 'Последние 7 дней'),
        ]
    
    # Добавляем часы через цикл
        for hours in range(1, 24):
            if hours == 1:
                label = f'Последний 1 час'
            elif 2 <= hours <= 4:
                label = f'Последние {hours} часа'
            else:
                label = f'Последние {hours} часов'
            lookups_list.append((f'last_{hours}_hour', label))
        return lookups_list


    def queryset(self, request, queryset):
    # Существующие условия...
        if self.value() == 'today':
            today = timezone.now().date()
            return queryset.filter(created_at__date=today)
        if self.value() == 'yesterday':
            yesterday = timezone.now().date() - timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        if self.value() == 'this_week':
            today = timezone.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            return queryset.filter(created_at__date__gte=start_of_week)
        if self.value() == 'this_month':
            today = timezone.now().date()
            start_of_month = today.replace(day=1)
            return queryset.filter(created_at__date__gte=start_of_month)
        if self.value() == 'last_24_hours':
            twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
            return queryset.filter(created_at__gte=twenty_four_hours_ago)
        if self.value() == 'last_7_days':
            seven_days_ago = timezone.now() - timedelta(days=7)
            return queryset.filter(created_at__gte=seven_days_ago)
    
    # Обработка часовых фильтров
        if self.value() and self.value().startswith('last_') and self.value().endswith('_hour'):
            try:
                hours = int(self.value().split('_')[1])
                hours_ago = timezone.now() - timedelta(hours=hours)
                return queryset.filter(created_at__gte=hours_ago)
            except (ValueError, IndexError):
                pass
        
        return queryset

@admin.register(Order)
class OrderAdmin(ModelAdminTotals):
    
    def get_list_display(self, request):
        """Динамическое отображение колонок в зависимости от фильтра"""
        base_list_display = (
            "order_number",
            "status",
            "created_at",
            "order_type",
            "discount",
            "total_sum",
            "payment_type_display",
            'created_by',
            'paid',
        )
        
        # Проверяем, применен ли фильтр по смешанной оплате
        if request.GET.get('payment_type__exact') == 'mixed':
            return base_list_display + ('cash_amount_display', 'online_amount_display')
        
        return base_list_display

    def get_list_totals(self, request):
        """Динамическое отображение итогов в зависимости от фильтра"""
        base_totals = [
            ("total_sum", lambda field: Coalesce(Sum(field), 0)),
        ]
        
        # Добавляем итоги для наличных и перевода только при фильтре mixed
        if request.GET.get('payment_type__exact') == 'mixed':
            base_totals.extend([
                ("cash_amount", lambda field: Coalesce(Sum(field), 0)),
                ("online_amount", lambda field: Coalesce(Sum(field), 0)),
            ])
        
        return base_totals

    def payment_type_display(self, obj):
        """Кастомное отображение типа оплаты с текстом для пустых значений"""
        if not obj.payment_type:
            return "Тип оплаты не выбран"
        return dict(Order.PAYMENT_TYPE_CHOICES).get(obj.payment_type, obj.payment_type)
    
    payment_type_display.short_description = "Оплата"
    payment_type_display.admin_order_field = "payment_type"

    def cash_amount_display(self, obj):
        """Отображение суммы наличной оплаты"""
        return f"{obj.cash_amount or 0} руб."
    
    cash_amount_display.short_description = "Наличные"
    cash_amount_display.admin_order_field = "cash_amount"

    def online_amount_display(self, obj):
        """Отображение суммы онлайн оплаты"""
        return f"{obj.online_amount or 0} руб."
    
    online_amount_display.short_description = "Перевод"
    online_amount_display.admin_order_field = "online_amount"
    
    readonly_fields = ('order_number','created_at','created_by',  "completion_time", 'cash_amount', 'online_amount')

    fieldsets = (
        (None, {
            'fields': ('order_number', 'status', 'created_at', 'order_type', 'payment_type')
        }),
        ('Информация о клиенте', {
            'fields': ('phone_number', 'name', 'address', 'table_number', 'comment')
        }),
        ('Финансы', {
            'fields': ('total_sum', 'discount', 'paid', 'cash_amount', 'online_amount')
        }),
        ('Дополнительно', {
            'fields': ('created_by', 'completion_time')
        }),
    )
    
    inlines = [OrderItemInline]
    list_display_links = [
        "order_number",
    ]
    search_fields = ["order_number"]
    list_filter = ["status", "order_type", DateTimeFilter, 'created_by', "payment_type"]

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
        "sales_report_link",
    )
    list_filter = (
        DateTimeFilter,
        "order__completed_at",
        "menu_item",
    )


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