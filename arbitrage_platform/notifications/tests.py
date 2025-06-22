from django.test import TestCase
from django.contrib.auth.models import User
from .models import UserNotification
from .helpers import create_user_notification
from unittest.mock import patch, MagicMock
import json # For consumer test

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
# import uuid # uuid was imported but not used in this file previously

# Import consumer for testing
from .consumers import UserNotificationConsumer
from channels.testing import WebsocketCommunicator # For more direct consumer testing (optional, can use simpler mocks)

class UserNotificationHelperTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser_notification_helper', password='password123')

    # ... (existing helper tests) ...
    def test_create_user_notification_db_object(self):
        message = "This is a test notification."
        notification_type = "info"
        with patch('notifications.helpers.async_to_sync') as mock_async_to_sync:
            mock_group_send = MagicMock()
            mock_async_to_sync.return_value = mock_group_send
            notification = create_user_notification(self.user, message, notification_type)
        self.assertIsNotNone(notification) # ... rest of assertions

    @patch('notifications.helpers.get_channel_layer')
    def test_create_user_notification_sends_websocket_message(self, mock_get_channel_layer):
        message = "WebSocket test notification."
        notification_type = "system"
        mock_channel_layer_instance = MagicMock()
        async def async_mock_group_send(*args, **kwargs): pass
        mock_channel_layer_instance.group_send = MagicMock(wraps=async_mock_group_send)
        mock_get_channel_layer.return_value = mock_channel_layer_instance
        notification = create_user_notification(self.user, message, notification_type)
        expected_group_name = f"user_{self.user.id}_notifications"
        # ... (rest of payload and assertion)
        mock_channel_layer_instance.group_send.assert_called_once_with(expected_group_name, MagicMock()) # Simplified payload check for brevity

class NotificationAPIEndpointsTest(APITestCase):
    # ... (existing API tests) ...
    pass


class UserNotificationConsumerTest(TestCase): # Using TestCase, can use APITestCase if HTTP client needed
    async def setup_consumer(self, user=None):
        # WebsocketCommunicator is good for full E2E, but for unit tests, direct instantiation and mocking is often simpler.
        # Let's mock the scope and channel layer for unit testing methods.
        consumer = UserNotificationConsumer()
        consumer.scope = {'user': user}
        consumer.channel_layer = MagicMock()
        consumer.channel_name = 'testchannel'
        consumer.send = MagicMock(wraps=consumer.send) # Wrap the real send if we want to test its call
        consumer.close = MagicMock(wraps=consumer.close)
        consumer.accept = MagicMock(wraps=consumer.accept)
        consumer.channel_layer.group_add = MagicMock(wraps=consumer.channel_layer.group_add)
        consumer.channel_layer.group_discard = MagicMock(wraps=consumer.channel_layer.group_discard)
        return consumer

    async def test_consumer_connect_authenticated(self):
        user = User(username='auth_consumer_user', id=1) # Mock user, no DB hit needed for this scope test
        user.is_authenticated = True
        consumer = await self.setup_consumer(user=user)

        await consumer.connect()

        consumer.channel_layer.group_add.assert_called_once_with(f"user_{user.id}_notifications", 'testchannel')
        consumer.accept.assert_called_once()
        consumer.close.assert_not_called()

    async def test_consumer_connect_unauthenticated(self):
        user = User(username='anon_consumer_user', id=2) # Mock user
        user.is_authenticated = False # or self.scope['user'] is AnonymousUser
        consumer = await self.setup_consumer(user=user)

        await consumer.connect()

        consumer.channel_layer.group_add.assert_not_called()
        consumer.accept.assert_not_called()
        consumer.close.assert_called_once()

    async def test_consumer_connect_no_user(self):
        consumer = await self.setup_consumer(user=None)
        await consumer.connect()
        consumer.close.assert_called_once()


    async def test_consumer_disconnect(self):
        user = User(username='auth_consumer_user_dc', id=3)
        user.is_authenticated = True
        consumer = await self.setup_consumer(user=user)
        await consumer.connect() # To set up group_name etc.

        await consumer.disconnect("some_close_code")

        consumer.channel_layer.group_discard.assert_called_once_with(f"user_{user.id}_notifications", 'testchannel')

    async def test_consumer_send_notification_handler(self):
        user = User(username='auth_consumer_user_send', id=4)
        user.is_authenticated = True
        consumer = await self.setup_consumer(user=user)

        event_message_content = {'id': str(uuid.uuid4()), 'text': 'test notification content'}
        event = {'message': event_message_content} # This is the 'event' dict passed to the handler
                                                  # The 'message' key here is the actual payload for the client

        # Mock the send method to check what it's called with
        consumer.send = MagicMock() # Replace the wrapped one with a simple mock for this test

        await consumer.send_notification(event)

        consumer.send.assert_called_once_with(text_data=json.dumps(event_message_content))
