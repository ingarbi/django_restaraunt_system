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
from decimal import Decimal, InvalidOperation

from .forms import OrderForm
from .models import MenuItem, Order, OrderItem


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
            # Сначала создаем заказ без сохранения
            order = form.save(commit=False)

            # Получаем данные из формы
            phone = request.POST.get("phone", "")
            first_name = request.POST.get("first_name", "")
            address = request.POST.get("addres", "")
            comment = request.POST.get("comment", "")
            payment_type = request.POST.get('payment_type')
            pay_later = request.POST.get('pay_later') == 'on'
            
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
                    order_items_data.append({
                        'menu_item': item,
                        'quantity': quantity
                    })

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
                    menu_item=item_data['menu_item'], 
                    quantity=item_data['quantity']
                )

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
                        "comment": order.comment,
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
            if order.paid:
                return JsonResponse({'success': False, 'message': 'Заказ уже оплачен'})
            
            # Get payment data from request
            try:
                data = json.loads(request.body)
            except Exception:
                return JsonResponse({'success': False, 'message': 'Неверные данные'})

            payment_type = data.get('payment_type')
            cash_received = Decimal(data.get('cash_received', 0))
            online_received = Decimal(data.get('online_received', 0))
            total = Decimal(data.get('total', 0))

            # Validate payment type
            if payment_type not in dict(Order.PAYMENT_TYPE_CHOICES):
                return JsonResponse({'success': False, 'message': 'Неверный тип оплаты'})

            if payment_type == 'cash':
                if cash_received < order.total_sum:
                    return JsonResponse({'success': False, 'message': 'Недостаточно наличных'})
                order.cash_amount = cash_received
                order.online_amount = 0
                order.paid = True
            
            elif payment_type == 'online':
                if online_received < order.total_sum:
                    return JsonResponse({'success': False, 'message': 'Недостаточно средств по переводу'})
                order.cash_amount = 0
                order.online_amount = online_received
                order.paid = True
                
            elif payment_type == 'mixed':
                    total_received = cash_received + online_received
                    if total_received < total:
                        return JsonResponse({'success': False, 'message': 'Общая сумма оплаты недостаточна'})
                    order.cash_amount = cash_received
                    order.online_amount = online_received
                    order.paid = True
            
            elif payment_type == 'free':
                order.cash_amount = 0
                order.online_amount = 0
                order.paid = True
            
            order.save()
            

            return JsonResponse({'success': True})
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Заказ не найден'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Недопустимый запрос'})