import os
import json

import weasyprint
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import datetime
from django.db.models import Sum
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth import get_user_model


from .forms import OrderForm
from .models import MenuItem, Order, OrderItem


User = get_user_model()

@login_required
def create_order(request):
    if request.user.profile.role != 'cashier' and request.user.profile.role != 'supervisor':
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
            # Save order items
            order = form.save()

            # Get order phone, name, adress
            phone = request.POST.get("phone", "")
            first_name = request.POST.get("first_name", "")
            address = request.POST.get("addres", "")
            payment_type = request.POST.get('payment_type')
            pay_later = request.POST.get('pay_later') == 'on'
            

                
            try:
                discount = int(request.POST.get("id_discount", 0))
            except:
                discount = 0

             # === СМЕШАННАЯ ОПЛАТА: получаем суммы ===
            cash_amount_raw = request.POST.get("cash_amount", "")
            online_amount_raw = request.POST.get("online_amount", "")
            payment_type = request.POST.get("payment_type", "")

            try:
                cash_amount = float(cash_amount_raw) if cash_amount_raw else 0
            except (ValueError, TypeError):
                cash_amount = 0
                
            try:
                online_amount = float(online_amount_raw) if online_amount_raw else 0
            except (ValueError, TypeError):
                online_amount = 0

            total_sum = 0
            for item in menu_items:
                
                quantity = int(request.POST.get(f"item_{item.id}", 0) or 0)
                if quantity > 0:
                    OrderItem.objects.create(
                        order=order, menu_item=item, quantity=quantity
                    )
                    total_sum += item.price * quantity

            order.discount = discount
            # Update the total sum of the order
            order.total_sum = total_sum - (total_sum * discount / 100)

            # Update order details
            order.phone_number = phone
            order.name = first_name
            order.address = address
            order.payment_type = payment_type
            order.created_by = request.user

            # === СМЕШАННАЯ ОПЛАТА: сохраняем суммы ===
            if payment_type == "mixed":
                order.cash_amount = cash_amount
                order.online_amount = online_amount
            else:
                order.cash_amount = None
                order.online_amount = None

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
                # Проверяем, что смешанная оплата покрывает заказ
                mixed_total = cash_amount + online_amount
                if mixed_total >= order.total_sum and mixed_total > 0:
                    order.paid = True
                else:
                    order.paid = False
            else:
                order.paid = False

            order.save()


            # Notify the kitchen about the new order
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "orders",
                {
                    "type": "order_update",
                    "message": "new_order",
                    "order_data": {
                        "id": order.id,
                        "order_number": order.order_number,
                        "status": order.status,
                        "paid": order.paid,
                        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "items": [
                            {"name": item.menu_item.name, "quantity": item.quantity}
                            for item in order.items.all()
                        ],
                    },
                },
            )
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": True, "order_id": order.id})
            return redirect("create_order")
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

    # Notify all clients about the status change
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "orders",
        {
            "type": "order_update",
            "action": "status_change",
            "order_id": order.id,
            "status": order.status,
            "paid": order.paid,
        },
    )

    return redirect("kitchen_orders")


def mark_order_delivered(request, order_id):
    order = Order.objects.get(id=order_id)

    # ПРОВЕРКА: нельзя выдать неоплаченный заказ
    if not order.paid:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "success": False, 
                "message": "Нельзя выдать заказ, пока он не оплачен. Сначала подтвердите оплату."
            })
        else:
            from django.contrib import messages
            messages.error(request, "Нельзя выдать заказ, пока он не оплачен.")
            return redirect("order_detail", order_id=order.id)



    order.status = "delivered"
    order.completed_at = timezone.now()
    order.save()

    # Notify all clients about the status change
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "orders",
        {
            "type": "order_update",
            "action": "status_change",
            "order_id": order.id,
            "status": order.status,
            "paid": order.paid,
        },
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": order.status})
    else:
        return redirect("all_orders")

def mark_order_cancelled(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = "cancelled"
    order.save()

    # Notify all clients about the status change
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "orders",
        {
            "type": "order_update",
            "action": "status_change",
            "order_id": order.id,
            "status": order.status,
            "paid": order.paid,
        },
    )

    return redirect("all_orders")

@login_required
def all_orders(request):
    if request.user.profile.role != 'cashier' and request.user.profile.role != 'supervisor':
        raise PermissionDenied("У вас нет доступа к этой странице.")
    # Get today's date
    today = timezone.now().date()
    # Filter orders created today and sort by status
    orders = Order.objects.filter(created_at__date=today).order_by(
        "status", "-created_at"
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Return only the partial HTML for AJAX requests
        html = render_to_string("orders/order_list.html", {"orders": orders})
        return JsonResponse({"html": html})

    return render(request, "orders/all_orders.html", {"orders": orders})

@login_required
def kitchen_orders(request):
    if request.user.profile.role != 'cook' and request.user.profile.role != 'supervisor':
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

    file_path = os.path.join(settings.BASE_DIR, "main/cafe_name.txt")
    cafe_name = ""
    try:
        with open(file_path, "r") as file:
            file_content = file.read()
           
            cafe_name = file_content
            
    except FileNotFoundError:
        cafe_name = "A&I SOFT"

    # Render the HTML template for the invoice
    html_string = render_to_string(
        "orders/order_pdf.html", {"order": order, "items": items, "CAFE_NAME":cafe_name}
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

def update_order_payment(request, order_id):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            order = Order.objects.get(id=order_id)
            
            data = json.loads(request.body)
            payment_type = data.get('payment_type')
            cash_received = float(data.get('cash_received', 0) or 0)
            online_received = float(data.get('online_received', 0) or 0)
            total = float(data.get('total', 0))
            
            if not payment_type:
                return JsonResponse({'success': False, 'message': 'Необходимо выбрать способ оплаты'})
            
            if payment_type == 'cash' and cash_received < total:
                return JsonResponse({'success': False, 'message': 'Недостаточно наличных средств'})
            
            if payment_type == 'online' and online_received < total:
                return JsonResponse({'success': False, 'message': 'Недостаточно средств по переводу'})
            
            if payment_type == 'mixed':
                mixed_total = cash_received + online_received
                if mixed_total < total:
                    return JsonResponse({'success': False, 'message': 'Общая сумма оплаты недостаточна'})
                if cash_received == 0 and online_received == 0:
                    return JsonResponse({'success': False, 'message': 'Укажите хотя бы одну сумму'})
                order.cash_amount = cash_received
                order.online_amount = online_received
            else:
                order.cash_amount = None
                order.online_amount = None
            
            order.payment_type = payment_type
            order.paid = True
            order.save()
            
            return JsonResponse({'success': True})
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Заказ не найден'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Недопустимый запрос'})


@staff_member_required
def stats_dashboard(request):
    # Получаем параметры фильтрации (множественный выбор)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    menu_item_ids = request.GET.getlist('menu_item')
    statuses = request.GET.getlist('status')
    order_types = request.GET.getlist('order_type')
    created_by_ids = request.GET.getlist('created_by')
    payment_types = request.GET.getlist('payment_type')

    # Базовый QuerySet для заказов
    orders_qs = Order.objects.select_related('created_by').order_by('-created_at')

    # Фильтр по дате
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            orders_qs = orders_qs.filter(created_at__date__gte=dt_from)
        except ValueError:
            dt_from = None
    else:
        dt_from = None

    if date_to:
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            orders_qs = orders_qs.filter(created_at__date__lte=dt_to)
        except ValueError:
            dt_to = None
    else:
        dt_to = None

    # Фильтр по блюдам (множественный)
    if menu_item_ids:
        orders_qs = orders_qs.filter(items__menu_item_id__in=menu_item_ids).distinct()

    # Фильтр по статусам (множественный)
    if statuses:
        orders_qs = orders_qs.filter(status__in=statuses)

    # Фильтр по типам заказа (множественный)
    if order_types:
        orders_qs = orders_qs.filter(order_type__in=order_types)

    # Фильтр по кассирам (множественный)
    if created_by_ids:
        orders_qs = orders_qs.filter(created_by_id__in=created_by_ids)
    
    # Фильтр по типам оплаты (множественный)
    if payment_types:
        orders_qs = orders_qs.filter(payment_type__in=payment_types)

    # Подсчёт общего количества и суммы (до пагинации)
    total_orders_count = orders_qs.count()
    total_orders_sum = orders_qs.aggregate(total=Sum('total_sum'))['total'] or 0

    # === БЛОК: Статистика по типам оплаты (с учётом смешанной) ===
    payment_stats = {
        'cash': 0,
        'online': 0,
        'free': 0,
    }
    
    # Проходим по всем отфильтрованным заказам
    for order in orders_qs:
        if order.payment_type == 'mixed':
            # Смешанная оплата: распределяем по частям
            payment_stats['cash'] += float(order.cash_amount or 0)
            payment_stats['online'] += float(order.online_amount or 0)
        elif order.payment_type == 'cash':
            payment_stats['cash'] += float(order.total_sum or 0)
        elif order.payment_type == 'online':
            payment_stats['online'] += float(order.total_sum or 0)
        elif order.payment_type == 'free':
            payment_stats['free'] += float(order.total_sum or 0)

    # Считаем проценты
    payment_percentages = {}
    for key, value in payment_stats.items():
        if total_orders_sum > 0:
            payment_percentages[key] = round(value / total_orders_sum * 100, 1)
        else:
            payment_percentages[key] = 0
    # === КОНЕЦ БЛОКА ===

    # Пагинация
    paginator = Paginator(orders_qs, 20)
    page = request.GET.get('page')
    try:
        orders_page = paginator.page(page)
    except PageNotAnInteger:
        orders_page = paginator.page(1)
    except EmptyPage:
        orders_page = paginator.page(paginator.num_pages)

    # Статистика по блюдам
    filtered_orders_ids = orders_qs.values_list('id', flat=True)
    order_items_qs = OrderItem.objects.filter(order_id__in=filtered_orders_ids)

    if menu_item_ids:
        order_items_qs = order_items_qs.filter(menu_item_id__in=menu_item_ids)

    product_stats = (
        order_items_qs
        .values('menu_item__id', 'menu_item__name')
        .annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(ExpressionWrapper(F('menu_item__price') * F('quantity'), output_field=DecimalField(max_digits=10, decimal_places=2)))
        )
        .order_by('-total_quantity')
    )

    # Списки для выпадающих фильтров
    all_menu_items = MenuItem.objects.all().order_by('name')
    status_choices = Order.STATUS_CHOICES
    order_type_choices = Order.ORDER_TYPE_CHOICES
    cashiers = User.objects.filter(orders_created__isnull=False).distinct().order_by('username')
    payment_type_choices = Order.PAYMENT_TYPE_CHOICES

    context = {
        'orders': orders_page,
        'total_orders_count': total_orders_count,
        'total_orders_sum': total_orders_sum,
        'product_stats': product_stats,
        'all_menu_items': all_menu_items,
        'selected_menu_items': menu_item_ids,
        'date_from': date_from,
        'date_to': date_to,
        'selected_statuses': statuses,
        'selected_order_types': order_types,
        'selected_cashiers': created_by_ids,
        'selected_payment_types': payment_types,
        'status_choices': status_choices,
        'order_type_choices': order_type_choices,
        'cashiers': cashiers,
        'payment_type_choices': payment_type_choices,
        'payment_stats': payment_stats,
        'payment_percentages': payment_percentages,
    }
    return render(request, 'orders/stats_dashboard.html', context)