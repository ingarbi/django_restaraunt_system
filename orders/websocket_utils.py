from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def send_order_update(order, message_type="order_update", action=None, extra_data=None):
    """
    Send WebSocket update for order changes
    """
    channel_layer = get_channel_layer()

    message_data = {
        "type": message_type,
        "order_id": order.id,
        "status": order.status,
        "paid": order.paid,
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
    }

    if action:
        message_data["action"] = action

    if extra_data:
        message_data.update(extra_data)

    async_to_sync(channel_layer.group_send)("orders", message_data)


def send_new_order_notification(order):
    """
    Send notification for a newly created order
    """
    send_order_update(
        order,
        message_type="order_update",
        action="new_order",
        extra_data={"message": "new_order"},
    )


def send_order_status_change(order, action):
    """
    Send notification for order status changes
    """
    send_order_update(order, message_type="order_update", action=action)
