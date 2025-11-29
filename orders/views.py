import json
import os
from datetime import timedelta
from decimal import Decimal

import pytz
import weasyprint
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import F, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from .forms import OrderForm
from .models import MenuItem, Order, OrderItem
from .websocket_utils import (send_new_order_notification,
                              send_order_status_change)


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
def get_cafe_name():
    """Получение названия кафе"""
    file_path = os.path.join(settings.BASE_DIR, "main/cafe_name.txt")
    try:
        with open(file_path, "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        return "A&I SOFT"


def apply_order_filters(orders, period_type, time_period, cashier_id):
    """Применение фильтров к заказам"""
    period_display = "за все время"
    cashier_display = "все кассиры"

    if cashier_id:
        try:
            cashier = User.objects.get(id=cashier_id)
            orders = orders.filter(created_by=cashier)
            cashier_display = f"кассир: {cashier.get_full_name() or cashier.username}"
        except User.DoesNotExist:
            pass

    if time_period and time_period.startswith("last_"):
        try:
            hours = int(time_period.split("_")[1])
            hours_ago = timezone.now() - timedelta(hours=hours)
            orders = orders.filter(created_at__gte=hours_ago)
            period_display = f"за последние {hours} часов"
        except (ValueError, IndexError):
            pass

    if period_type:
        today = timezone.now().date()

        period_filters = {
            "today": (today, "за сегодня"),
            "yesterday": (today - timedelta(days=1), "за вчера"),
            "day_before_yesterday": (today - timedelta(days=2), "за позавчера"),
            "week": (today - timedelta(days=today.weekday()), "за эту неделю"),
            "month": (today.replace(day=1), "за этот месяц"),
            "year": (today.replace(month=1, day=1), "за этот год"),
        }

        if period_type in period_filters:
            filter_date, display_text = period_filters[period_type]
            orders = orders.filter(created_at__date__gte=filter_date)
            period_display = display_text

    return orders, period_display, cashier_display


def get_order_statistics(orders):
    """Получение статистики по заказам"""
    # Общая статистика
    total_revenue = orders.aggregate(total=Sum("total_sum"))["total"] or 0
    orders_count = orders.count()
    average_order_value = total_revenue / orders_count if orders_count > 0 else 0

    # Статистика по типам оплаты
    cash_total = (
        orders.filter(payment_type="cash").aggregate(total=Sum("total_sum"))["total"]
        or 0
    )
    online_total = (
        orders.filter(payment_type="online").aggregate(total=Sum("total_sum"))["total"]
        or 0
    )

    # Для смешанной оплаты
    mixed_orders = orders.filter(payment_type="mixed")
    cash_total += mixed_orders.aggregate(total=Sum("cash_amount"))["total"] or 0
    online_total += mixed_orders.aggregate(total=Sum("online_amount"))["total"] or 0

    # НОВАЯ СТАТИСТИКА: Суммы бесплатных и неоплаченных заказов
    free_orders_total = (
        orders.filter(payment_type="free").aggregate(total=Sum("total_sum"))["total"]
        or 0
    )

    unpaid_orders_total = (
        orders.filter(paid=False).aggregate(total=Sum("total_sum"))["total"] or 0
    )

    # Данные по продажам
    sales_data = (
        OrderItem.objects.filter(
            order__in=orders,
            order__status="delivered",
        )
        .values("menu_item__name")
        .annotate(
            total_quantity=Sum("quantity"),
            total_revenue=Sum(F("quantity") * F("menu_item__price")),
        )
        .order_by("-total_quantity")
    )

    return {
        "total_revenue": total_revenue,
        "orders_count": orders_count,
        "average_order_value": average_order_value,
        "cash_total": cash_total,
        "online_total": online_total,
        "free_orders_total": free_orders_total,
        "unpaid_orders_total": unpaid_orders_total,
        "sales_data": sales_data,
    }


# ОСНОВНЫЕ ФУНКЦИИ ПРЕДСТАВЛЕНИЙ
@login_required
def create_order(request):
    if (
        request.user.profile.role != "cashier"
        and request.user.profile.role != "supervisor"
    ):
        raise PermissionDenied("У вас нет доступа к этой странице.")

    menu_items = MenuItem.objects.all().select_related("category")
    menu_items_by_category = {}
    for item in menu_items:
        if item.category.name not in menu_items_by_category:
            menu_items_by_category[item.category.name] = []
        menu_items_by_category[item.category.name].append(item)

    if request.method == "POST":
        form = OrderForm(request.POST)
        if form.is_valid():
            # Сначала создаем заказ без сохранения
            order = form.save(commit=False)

            # Получаем данные из формы
            phone = request.POST.get("phone", "")
            first_name = request.POST.get("first_name", "")
            address = request.POST.get("addres", "")
            comment = request.POST.get("comment", "")
            payment_type = request.POST.get("payment_type")
            pay_later = request.POST.get("pay_later") == "on"

            try:
                discount = int(request.POST.get("id_discount", 0))
            except:
                discount = 0

            # Получаем суммы для смешанной оплаты
            cash_amount = request.POST.get("cash_amount", 0)
            online_amount = request.POST.get("online_amount", 0)

            # Рассчитываем общую сумму заказа
            total_sum = 0
            order_items_data = []  # Сохраняем данные о товарах временно

            for item in menu_items:
                quantity = int(request.POST.get(f"item_{item.id}", 0) or 0)
                if quantity > 0:
                    total_sum += item.price * quantity
                    order_items_data.append({"menu_item": item, "quantity": quantity})

            # Устанавливаем основные данные заказа
            order.discount = discount
            order.total_sum = total_sum - (total_sum * discount / 100)
            order.phone_number = phone
            order.name = first_name
            order.address = address
            order.comment = comment
            order.payment_type = payment_type
            order.created_by = request.user

            # Сохраняем суммы смешанной оплаты
            if payment_type == "mixed":
                try:
                    order.cash_amount = float(cash_amount) if cash_amount else 0
                    order.online_amount = float(online_amount) if online_amount else 0

                except (ValueError, TypeError):
                    order.cash_amount = 0
                    order.online_amount = 0
            elif payment_type == "cash":
                print(cash_amount, online_amount)
                order.cash_amount = order.total_sum
                order.online_amount = 0
            elif payment_type == "online":
                order.cash_amount = 0
                order.online_amount = order.total_sum
            else:
                order.cash_amount = 0
                order.online_amount = 0
            table_number = request.POST.get("table_number") or None
            if order.order_type == "dine_in":
                order.table_number = table_number

            # 🔑 Payment status logic
            if pay_later:
                order.paid = False
            elif payment_type in ["online", "free"]:
                order.paid = True
            elif payment_type == "cash" and not pay_later:
                order.paid = True
            elif payment_type == "mixed":
                # Для смешанной оплаты проверяем, покрывает ли сумма заказ
                mixed_total = order.cash_amount + order.online_amount
                if mixed_total >= order.total_sum:
                    order.paid = True
                else:
                    order.paid = False
            else:
                order.paid = False

            # СОХРАНЯЕМ ЗАКАЗ ПЕРВЫМ!
            order.save()

            # Теперь создаем OrderItem после сохранения заказа
            for item_data in order_items_data:
                OrderItem.objects.create(
                    order=order,
                    menu_item=item_data["menu_item"],
                    quantity=item_data["quantity"],
                )

            send_new_order_notification(order)

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": True, "order_id": order.id})
            return redirect("create_order")
        else:
            # Если форма невалидна, возвращаем ошибку
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "errors": form.errors})
    else:
        context = {
            "menu_items_by_category": menu_items_by_category,
        }
        return render(request, "orders/create_order.html", context=context)


def mark_order_completed(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = "done"
    order.completed_at = timezone.now()
    order.save()

    send_order_status_change(order, "status_change")
    return redirect("kitchen_orders")


def mark_order_delivered(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = "delivered"
    order.completed_at = timezone.now()
    order.save()

    send_order_status_change(order, "status_change")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": order.status})
    else:
        return redirect("all_orders")


def mark_order_cancelled(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = "cancelled"
    order.save()

    send_order_status_change(order, "status_change")
    return redirect("all_orders")


@login_required
def all_orders(request):
    if request.user.profile.role not in ["cashier", "supervisor"]:
        raise PermissionDenied("У вас нет доступа к этой странице.")

    msk_tz = pytz.timezone("Europe/Moscow")
    now_msk = timezone.now().astimezone(msk_tz)
    #today = now_msk.date()
    twenty_eight_hours_ago = now_msk - timedelta(hours=27)

    # Filter orders created today and sort by status
    orders = Order.objects.filter(created_at__gte=twenty_eight_hours_ago).order_by(
        "status", "-created_at"
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Return only the partial HTML for AJAX requests
        html = render_to_string("orders/order_list.html", {"orders": orders})
        return JsonResponse({"html": html})

    return render(request, "orders/all_orders.html", {"orders": orders})


@login_required
def kitchen_orders(request):
    if request.user.profile.role not in ["cook", "supervisor"]:
        raise PermissionDenied("У вас нет доступа к этой странице.")

    orders = Order.objects.filter(status="pending")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Return only the partial HTML for AJAX requests
        html = render_to_string("orders/kitchen_order_list.html", {"orders": orders})
        return JsonResponse({"html": html})

    return render(request, "orders/kitchen_orders.html", {"orders": orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__menu_item"), id=order_id
    )
    return render(request, "orders/order_detail.html", {"order": order})


def order_pdf(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    items = order.items.select_related("menu_item")

    cafe_name = get_cafe_name()

    # Render the HTML template for the invoice
    html_string = render_to_string(
        "orders/order_pdf.html",
        {"order": order, "items": items, "CAFE_NAME": cafe_name},
    )

    # Generate the PDF
    pdf_file = weasyprint.HTML(string=html_string).write_pdf(
        stylesheets=[weasyprint.CSS("static/css/order_pdf.css")]
    )

    # Create the HTTP response with the PDF file
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="invoice_order_{order.order_number}.pdf"'
    )
    return response


def quick_receipt_printing(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__menu_item"), id=order_id
    )
    return render(request, "orders/quick_receipt_printing.html", {"order": order})


def big_reports_printing(request):
    """
    Print detailed report (similar to your current reports page but print-optimized)
    """
    # Reuse the same filtering logic from your reports view
    period_type = request.GET.get("period_type", "")
    time_period = request.GET.get("time_period", "")
    cashier_id = request.GET.get("cashier", "")

    # Reuse the same filtering logic from your reports view
    orders = Order.objects.all()
    period_display = "за все время"
    cashier_display = "все кассиры"

    # Apply filters (copy the same logic from your reports view)
    if cashier_id:
        try:
            cashier = User.objects.get(id=cashier_id)
            orders = orders.filter(created_by=cashier)
            cashier_display = f"кассир: {cashier.get_full_name() or cashier.username}"
        except User.DoesNotExist:
            pass

    if time_period and time_period.startswith("last_"):
        try:
            hours_str = time_period.split("_")[1]
            hours = int(hours_str)
            hours_ago = timezone.now() - timedelta(hours=hours)
            orders = orders.filter(created_at__gte=hours_ago)
            if hours == 1:
                period_display = f"за последний 1 час"
            elif 2 <= hours <= 4:
                period_display = f"за последние {hours} часа"
            else:
                period_display = f"за последние {hours} часов"
        except (ValueError, IndexError):
            pass
    elif period_type:
        if period_type == "today":
            today = timezone.now().date()
            orders = orders.filter(created_at__date=today)
            period_display = "за сегодня"
        elif period_type == "yesterday":
            yesterday = timezone.now().date() - timedelta(days=1)
            orders = orders.filter(created_at__date=yesterday)
            period_display = "за вчера"
        elif period_type == "day_before_yesterday":
            day_before_yesterday = timezone.now().date() - timedelta(days=2)
            orders = orders.filter(created_at__date=day_before_yesterday)
            period_display = "за позавчера"
        elif period_type == "week":
            today = timezone.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            orders = orders.filter(created_at__date__gte=start_of_week)
            period_display = "за эту неделю"
        elif period_type == "month":
            today = timezone.now().date()
            start_of_month = today.replace(day=1)
            orders = orders.filter(created_at__date__gte=start_of_month)
            period_display = "за этот месяц"
        elif period_type == "year":
            today = timezone.now().date()
            start_of_year = today.replace(month=1, day=1)
            orders = orders.filter(created_at__date__gte=start_of_year)
            period_display = "за этот год"

    # Get cafe name
    file_path = os.path.join(settings.BASE_DIR, "main/cafe_name.txt")
    cafe_name = ""
    try:
        with open(file_path, "r") as file:
            cafe_name = file.read()
    except FileNotFoundError:
        cafe_name = "A&I SOFT"

    # Get sales data
    sales_data = (
        OrderItem.objects.filter(
            order__in=orders,
            order__status="delivered",
        )
        .values("menu_item__name", "menu_item__price")
        .annotate(
            total_quantity=Sum("quantity"),
            total_revenue=Sum(F("quantity") * F("menu_item__price")),
        )
        .order_by("-total_quantity")
    )

    # Calculate totals
    total_revenue = orders.aggregate(total=Sum("total_sum"))["total"] or 0
    orders_count = orders.count()
    average_order_value = total_revenue / orders_count if orders_count > 0 else 0

    cash_total = (
        orders.filter(payment_type="cash").aggregate(total=Sum("total_sum"))["total"]
        or 0
    )
    online_total = (
        orders.filter(payment_type="online").aggregate(total=Sum("total_sum"))["total"]
        or 0
    )
    
    free_orders_total = (
        orders.filter(payment_type="free").aggregate(total=Sum("total_sum"))["total"]
        or 0
    )

    unpaid_orders_total = (
        orders.filter(paid=False).aggregate(total=Sum("total_sum"))["total"] or 0
    )
    cancelled_orders_total = (
        orders.filter(status="cancelled").aggregate(total=Sum("total_sum"))["total"] or 0
    )

    mixed_orders = orders.filter(payment_type="mixed")
    cash_total += mixed_orders.aggregate(total=Sum("cash_amount"))["total"] or 0
    online_total += mixed_orders.aggregate(total=Sum("online_amount"))["total"] or 0

    context = {
        "orders": orders.order_by("-created_at"),
        "sales_data": sales_data,
        "period_display": period_display,
        "cashier_display": cashier_display,
        "total_revenue": total_revenue,
        "orders_count": orders_count,
        "average_order_value": average_order_value,
        "cash_total": cash_total,
        "online_total": online_total,
        "free_orders_total": free_orders_total,
        "unpaid_orders_total": unpaid_orders_total,
        "cancelled_orders_total":cancelled_orders_total,
        "CAFE_NAME": cafe_name,
    }

    return render(request, "orders/big_reports_printing.html", context)


def short_reports_printing(request):
    """
    Print summary report (only key statistics)
    """
    # Reuse the same filtering logic from big_reports_printing
    period_type = request.GET.get("period_type", "")
    time_period = request.GET.get("time_period", "")
    cashier_id = request.GET.get("cashier", "")

    orders = Order.objects.all()
    period_display = "за все время"
    cashier_display = "все кассиры"

    # Apply filters (same as above)
    if cashier_id:
        try:
            cashier = User.objects.get(id=cashier_id)
            orders = orders.filter(created_by=cashier)
            cashier_display = f"кассир: {cashier.get_full_name() or cashier.username}"
        except User.DoesNotExist:
            pass

    if time_period and time_period.startswith("last_"):
        try:
            hours_str = time_period.split("_")[1]
            hours = int(hours_str)
            hours_ago = timezone.now() - timedelta(hours=hours)
            orders = orders.filter(created_at__gte=hours_ago)
            if hours == 1:
                period_display = f"за последний 1 час"
            elif 2 <= hours <= 4:
                period_display = f"за последние {hours} часа"
            else:
                period_display = f"за последние {hours} часов"
        except (ValueError, IndexError):
            pass
    elif period_type:
        if period_type == "today":
            today = timezone.now().date()
            orders = orders.filter(created_at__date=today)
            period_display = "за сегодня"
        elif period_type == "yesterday":
            yesterday = timezone.now().date() - timedelta(days=1)
            orders = orders.filter(created_at__date=yesterday)
            period_display = "за вчера"
        elif period_type == "day_before_yesterday":
            day_before_yesterday = timezone.now().date() - timedelta(days=2)
            orders = orders.filter(created_at__date=day_before_yesterday)
            period_display = "за позавчера"
        elif period_type == "week":
            today = timezone.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            orders = orders.filter(created_at__date__gte=start_of_week)
            period_display = "за эту неделю"
        elif period_type == "month":
            today = timezone.now().date()
            start_of_month = today.replace(day=1)
            orders = orders.filter(created_at__date__gte=start_of_month)
            period_display = "за этот месяц"
        elif period_type == "year":
            today = timezone.now().date()
            start_of_year = today.replace(month=1, day=1)
            orders = orders.filter(created_at__date__gte=start_of_year)
            period_display = "за этот год"

    # Calculate totals only (no detailed data)
    total_revenue = orders.aggregate(total=Sum("total_sum"))["total"] or 0
    orders_count = orders.count()
    average_order_value = total_revenue / orders_count if orders_count > 0 else 0

    cash_total = (
        orders.filter(payment_type="cash").aggregate(total=Sum("total_sum"))["total"]
        or 0
    )
    online_total = (
        orders.filter(payment_type="online").aggregate(total=Sum("total_sum"))["total"]
        or 0
    )

    free_orders_total = (
        orders.filter(payment_type="free").aggregate(total=Sum("total_sum"))["total"]
        or 0
    )

    unpaid_orders_total = (
        orders.filter(paid=False).aggregate(total=Sum("total_sum"))["total"] or 0
    )
    cancelled_orders_total = (
        orders.filter(status="cancelled").aggregate(total=Sum("total_sum"))["total"] or 0
    )

    mixed_orders = orders.filter(payment_type="mixed")
    cash_total += mixed_orders.aggregate(total=Sum("cash_amount"))["total"] or 0
    online_total += mixed_orders.aggregate(total=Sum("online_amount"))["total"] or 0

    # Get cafe name
    file_path = os.path.join(settings.BASE_DIR, "main/cafe_name.txt")
    cafe_name = ""
    try:
        with open(file_path, "r") as file:
            cafe_name = file.read()
    except FileNotFoundError:
        cafe_name = "A&I SOFT"

    context = {
        "period_display": period_display,
        "cashier_display": cashier_display,
        "total_revenue": total_revenue,
        "orders_count": orders_count,
        "average_order_value": average_order_value,
        "cash_total": cash_total,
        "online_total": online_total,
        "free_orders_total": free_orders_total,  
        "unpaid_orders_total": unpaid_orders_total,
        "cancelled_orders_total":cancelled_orders_total,
        "CAFE_NAME": cafe_name,
    }

    return render(request, "orders/short_reports_printing.html", context)


def update_order_payment(request, order_id):
    if (
        request.method == "POST"
        and request.headers.get("X-Requested-With") == "XMLHttpRequest"
    ):
        try:
            order = Order.objects.get(id=order_id)
            if order.paid:
                return JsonResponse({"success": False, "message": "Заказ уже оплачен"})

            # Get payment data from request
            try:
                data = json.loads(request.body)
            except Exception:
                return JsonResponse({"success": False, "message": "Неверные данные"})

            payment_type = data.get("payment_type")
            cash_received = Decimal(data.get("cash_received", 0))
            online_received = Decimal(data.get("online_received", 0))
            total = Decimal(data.get("total", 0))

            # Validate payment type
            if payment_type not in dict(Order.PAYMENT_TYPE_CHOICES):
                return JsonResponse(
                    {"success": False, "message": "Неверный тип оплаты"}
                )

            order.payment_type = payment_type

            if payment_type == "cash":
                if cash_received < order.total_sum:
                    return JsonResponse(
                        {"success": False, "message": "Недостаточно наличных"}
                    )
                order.cash_amount = cash_received
                order.online_amount = 0
                order.paid = True

            elif payment_type == "online":
                if online_received < order.total_sum:
                    return JsonResponse(
                        {
                            "success": False,
                            "message": "Недостаточно средств по переводу",
                        }
                    )
                order.cash_amount = 0
                order.online_amount = online_received
                order.paid = True

            elif payment_type == "mixed":
                total_received = cash_received + online_received
                if total_received < total:
                    return JsonResponse(
                        {"success": False, "message": "Общая сумма оплаты недостаточна"}
                    )
                order.cash_amount = cash_received
                order.online_amount = online_received
                order.paid = True

            elif payment_type == "free":
                order.cash_amount = 0
                order.online_amount = 0
                order.paid = True

            order.save()

            return JsonResponse({"success": True})
        except Order.DoesNotExist:
            return JsonResponse({"success": False, "message": "Заказ не найден"})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

    return JsonResponse({"success": False, "message": "Недопустимый запрос"})


@login_required
def reports(request):
    if request.user.profile.role not in ["cashier", "supervisor"]:
        raise PermissionDenied("У вас нет доступа к этой странице.")

    # Получаем параметры фильтрации
    period_type = request.GET.get("period_type", "")
    time_period = request.GET.get("time_period", "")
    cashier_id = request.GET.get("cashier", "")

    # Базовый queryset для заказов
    orders = Order.objects.all()
    orders, period_display, cashier_display = apply_order_filters(
        orders, period_type, time_period, cashier_id
    )

    # Получаем статистику
    statistics = get_order_statistics(orders)

    cashiers = User.objects.filter(
        profile__role__in=["cashier", "supervisor"]
    ).order_by("username")

    # Генерируем список выбора временных периодов
    time_period_choices = [("", "---")]
    for i in range(1, 24):
        if i == 1:
            time_period_choices.append((f"last_{i}_hour", f"Последний {i} час"))
        elif i < 5:
            time_period_choices.append((f"last_{i}_hours", f"Последние {i} часа"))
        else:
            time_period_choices.append((f"last_{i}_hours", f"Последние {i} часов"))

    context = {
        "title": "Отчеты по заказам",
        "orders": orders.order_by("-created_at"),
        "period_display": period_display,
        "cashier_display": cashier_display,
        "period_type": period_type,
        "time_period": time_period,
        "cashier_id": cashier_id,
        "cashiers": cashiers,
        "time_period_choices": time_period_choices,
        **statistics,
    }
    return render(request, "orders/reports.html", context)
