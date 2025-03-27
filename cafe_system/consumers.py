from channels.generic.websocket import AsyncWebsocketConsumer
import json


class OrderConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join a group for all orders
        self.group_name = "orders"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        pass  # Not needed for this use case

    async def order_update(self, event):
        print(event)
        # Send order updates to the client
        await self.send(text_data=json.dumps(event))

    # Send message to WebSocket
    async def send_order_update(self, event):
        message = event['message']
        order_data = event.get('order_data', {})  # Include order details if needed
        # await self.send(text_data=json.dumps({
        #     'message': message,
        #     'order_data': order_data
        # }))
        print(message)
        print(order_data)