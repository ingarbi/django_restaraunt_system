from datetime import timedelta

import django_filters
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Order


class DateTimeFilter(django_filters.FilterSet):
    TIME_PERIOD_CHOICES = [
        ("", "---"),  # Пустой выбор по умолчанию
        ("last_1_hour", "Последний 1 час"),
        ("last_2_hours", "Последние 2 часа"),
        ("last_3_hours", "Последние 3 часа"),
        ("last_4_hours", "Последние 4 часа"),
        ("last_5_hours", "Последние 5 часов"),
        ("last_6_hours", "Последние 6 часов"),
        ("last_7_hours", "Последние 7 часов"),
        ("last_8_hours", "Последние 8 часов"),
        ("last_9_hours", "Последние 9 часов"),
        ("last_10_hours", "Последние 10 часов"),
        ("last_11_hours", "Последние 11 часов"),
        ("last_12_hours", "Последние 12 часов"),
        ("last_13_hours", "Последние 13 часов"),
        ("last_14_hours", "Последние 14 часов"),
        ("last_15_hours", "Последние 15 часов"),
        ("last_16_hours", "Последние 16 часов"),
        ("last_17_hours", "Последние 17 часов"),
        ("last_18_hours", "Последние 18 часов"),
        ("last_19_hours", "Последние 19 часов"),
        ("last_20_hours", "Последние 20 часов"),
        ("last_21_hours", "Последние 21 час"),
        ("last_22_hours", "Последние 22 часа"),
        ("last_23_hours", "Последние 23 часа"),
    ]

    time_period = django_filters.ChoiceFilter(
        choices=TIME_PERIOD_CHOICES,
        method="filter_by_time_period",
        label="Период времени",
    )
    cashier = django_filters.ModelChoiceFilter(
        field_name="created_by",
        queryset=User.objects.filter(
            profile__role__in=["cashier", "supervisor"]
        ).order_by("username"),
        label="Кассир",
        method="filter_by_cashier",
    )

    class Meta:
        model = Order
        fields = ["time_period", "cashier"]

    def filter_by_time_period(self, queryset, name, value):
        if value and value.startswith("last_"):
            try:
                hours = int(value.split("_")[1])
                hours_ago = timezone.now() - timedelta(hours=hours)
                return queryset.filter(created_at__gte=hours_ago)
            except (ValueError, IndexError):
                pass
        return queryset
    
    def filter_by_cashier(self, queryset, name, value):
        if value:
            return queryset.filter(created_by=value)
        return queryset
