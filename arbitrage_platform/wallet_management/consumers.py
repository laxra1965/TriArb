import json
from channels.generic.websocket import AsyncWebsocketConsumer

class WalletConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if self.user is None or not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = f"user_{self.user.id}_wallet"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"User {self.user.id} connected to wallet WebSocket.") # Logging

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            print(f"User {self.user.id} disconnected from wallet WebSocket.") # Logging

    async def send_wallet_update(self, event): # Matches 'type' in group_send
        message_data = event['message']
        await self.send(text_data=json.dumps(message_data))
        print(f"Sent wallet update to user {self.user.id}: {message_data}") # Logging
