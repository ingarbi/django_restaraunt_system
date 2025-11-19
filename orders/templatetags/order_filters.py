from django import template

register = template.Library()

@register.filter
def dictsum(queryset, field_name):
    """Суммирует значения поля в queryset"""
    return sum(getattr(item, field_name, 0) for item in queryset)

@register.filter
def divide(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def sum_quantity(sales_data):
    return sum(item['total_quantity'] for item in sales_data)

@register.filter
def sum_revenue(sales_data):
    return sum(item['total_revenue'] for item in sales_data)

@register.filter
def dictsum(value, arg):
    return sum(item[arg] for item in value)