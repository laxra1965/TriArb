import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TradeStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if self.user is None or not self.user.is_authenticated:
            await self.close()
            return

        # For trades, a user might be interested in all their trades,
        # or specific trade attempts. A group per user is simplest for now.
        self.group_name = f"user_{self.user.id}_trades"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"User {self.user.id} connected to trades WebSocket.") # Logging


    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            print(f"User {self.user.id} disconnected from trades WebSocket.") # Logging

    async def send_trade_update(self, event): # Matches 'type'
        message_data = event['message']
        await self.send(text_data=json.dumps(message_data))
        print(f"Sent trade update to user {self.user.id}: {message_data}") # Logging
