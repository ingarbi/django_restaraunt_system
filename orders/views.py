from django.shortcuts import render, redirect
from .models import Order, MenuItem, OrderItem
from .forms import OrderForm
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.template.loader import render_to_string

def create_order(request):
    menu_items = MenuItem.objects.all().select_related('category')
    menu_items_by_category = {}
    for item in menu_items:
        if item.category.name not in menu_items_by_category:
            menu_items_by_category[item.category.name] = []
        menu_items_by_category[item.category.name].append(item)

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Save order items
            order = form.save()

            # Get order phone, name, adress
            phone = request.POST.get('phone', "")
            first_name = request.POST.get('first_name', "")
            address = request.POST.get('addres', "")

            total_sum = 0
            for item in menu_items:
                quantity = int(request.POST.get(f'item_{item.id}', 0))
                if quantity > 0:
                    OrderItem.objects.create(order=order, menu_item=item, quantity=quantity)
                    total_sum += item.price * quantity
                    
            # Update the total sum of the order
            order.total_sum = total_sum
            
            # Update order details
            order.phone_number = phone
            order.name  = first_name
            order.address = address
            
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
                        "created_at": order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        "items": [
                            {"name": item.menu_item.name, "quantity": item.quantity}
                            for item in order.items.all()
                        ]
                    }
                }
            )
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('create_order')
    else:
        context = {'menu_items_by_category': menu_items_by_category, }
        return render(request, 'orders/create_order.html', context=context)

          

def mark_order_completed(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = "done"
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
        },
    )

    return redirect('kitchen_orders')

def mark_order_delivered(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = "delivered"
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
        },
    )

    return redirect('all_orders')

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
        },
    )

    return redirect('all_orders')

def all_orders(request):
    # Get today's date
    today = timezone.now().date()
    # Filter orders created today and sort by status
    orders = Order.objects.filter(created_at__date=today).order_by('status', '-created_at')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return only the partial HTML for AJAX requests
        html = render_to_string('orders/order_list.html', {'orders': orders})
        return JsonResponse({'html': html})
    
    return render(request, 'orders/all_orders.html', {'orders': orders})

def kitchen_orders(request):
    orders = Order.objects.filter(status="pending")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return only the partial HTML for AJAX requests
        html = render_to_string('orders/kitchen_order_list.html', {'orders': orders})
        return JsonResponse({'html': html})
    return render(request, 'orders/kitchen_orders.html', {'orders': orders})