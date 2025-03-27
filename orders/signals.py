from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


@receiver(post_save, sender=Order)
def new_order(sender, instance, created, **kwargs):
    pass
    # Notify the kitchen about the new order
    # print(instance.id)
    # channel_layer = get_channel_layer()
    # async_to_sync(channel_layer.group_send)(
    #     "orders",
    #     {
    #         "type": "order_update",
    #         "message": {
    #             "action": "new_order",
    #             "order_id": instance.id,
    #             "order_number": instance.order_number,
    #             "status": instance.status
    #         },
    #     },
    # )