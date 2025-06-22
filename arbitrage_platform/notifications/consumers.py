import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async # For accessing Django ORM

class UserNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user") # AuthMiddlewareStack provides user

        if self.user is None or not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = f"user_{self.user.id}_notifications"

        # Join user-specific group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        # print(f"User {self.user.id} connected to notifications WebSocket.")

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            # print(f"User {self.user.id} disconnected from notifications WebSocket.")


    # Receive message from WebSocket (client -> server) - not strictly needed for broadcast only
    # async def receive(self, text_data):
    #     pass # Handle incoming messages if necessary

    # Handler for messages sent to the group (server -> client)
    async def send_notification(self, event):
        message_data = event['message'] # 'message' is the key used in group_send

        # Send message to WebSocket
        await self.send(text_data=json.dumps(message_data))
        # print(f"Sent notification to user {self.user.id}: {message_data}")
