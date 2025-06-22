from django.test import TestCase
from django.contrib.auth.models import User
from .models import UserWallet, WalletTransaction, WalletDepositRequest
import decimal
from django.db import IntegrityError # For testing signals if user is deleted
from django.core.exceptions import ValidationError # For full_clean test
from unittest.mock import patch, MagicMock # For consumer and signal tests
import json # For consumer tests

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings


class UserWalletModelSignalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_with_signal_wallet = User.objects.create_user(username='testuser_wallet_signal', password='password123')

    def test_wallet_creation_on_user_create(self):
        self.assertTrue(hasattr(self.user_with_signal_wallet, 'wallet'))
        self.assertIsInstance(self.user_with_signal_wallet.wallet, UserWallet)
        self.assertEqual(self.user_with_signal_wallet.wallet.balance, decimal.Decimal('0.0'))

    def test_save_user_wallet_signal_idempotency(self):
        initial_wallet_id = self.user_with_signal_wallet.wallet.id
        self.user_with_signal_wallet.email = "newemail@example.com"
        self.user_with_signal_wallet.save()
        self.user_with_signal_wallet.refresh_from_db()
        self.assertTrue(hasattr(self.user_with_signal_wallet, 'wallet'))
        self.assertEqual(self.user_with_signal_wallet.wallet.id, initial_wallet_id)


class UserWalletMethodTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser_wallet_methods', password='password123')
        cls.wallet = UserWallet.objects.get(user=cls.user)

    @patch('wallet_management.models.get_channel_layer') # Path to where get_channel_layer is imported in models.py
    def test_add_credit_broadcasts_update(self, mock_get_channel_layer):
        initial_balance = self.wallet.balance
        amount_to_add = decimal.Decimal('100.50')
        description = "Test deposit with broadcast"

        mock_channel_layer_instance = MagicMock()
        async def async_mock_group_send(*args, **kwargs): pass # Mock async behavior
        mock_channel_layer_instance.group_send = MagicMock(wraps=async_mock_group_send)
        mock_get_channel_layer.return_value = mock_channel_layer_instance

        self.wallet.add_credit(amount_to_add, description=description)
        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, initial_balance + amount_to_add)
        # ... (rest of transaction assertions from previous version) ...

        mock_get_channel_layer.assert_called_once()
        expected_group_name = f"user_{self.user.id}_wallet"
        expected_payload_message_content = {
            'user_id': self.user.id,
            'balance': str(self.wallet.balance),
            'last_updated': self.wallet.updated_at.isoformat(),
            'description': description,
            'transaction_type': 'credit',
            'transaction_amount': str(amount_to_add)
        }
        mock_channel_layer_instance.group_send.assert_called_once_with(
            expected_group_name,
            {'type': 'send_wallet_update', 'message': expected_payload_message_content}
        )

    @patch('wallet_management.models.get_channel_layer')
    def test_deduct_credit_broadcasts_update(self, mock_get_channel_layer):
        self.wallet.add_credit(decimal.Decimal('200.0')) # Ensure balance
        self.wallet.refresh_from_db()
        initial_balance_before_deduct = self.wallet.balance
        amount_to_deduct = decimal.Decimal('50.25')
        description = "Test withdrawal with broadcast"

        mock_channel_layer_instance = MagicMock()
        async def async_mock_group_send(*args, **kwargs): pass
        mock_channel_layer_instance.group_send = MagicMock(wraps=async_mock_group_send)
        mock_get_channel_layer.return_value = mock_channel_layer_instance

        self.wallet.deduct_credit(amount_to_deduct, description=description)
        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, initial_balance_before_deduct - amount_to_deduct)
        # ... (rest of transaction assertions) ...

        mock_get_channel_layer.assert_called_once()
        expected_group_name = f"user_{self.user.id}_wallet"
        expected_payload_message_content = {
            'user_id': self.user.id,
            'balance': str(self.wallet.balance),
            'last_updated': self.wallet.updated_at.isoformat(),
            'description': description,
            'transaction_type': 'debit',
            'transaction_amount': str(amount_to_deduct)
        }
        mock_channel_layer_instance.group_send.assert_called_once_with(
            expected_group_name,
            {'type': 'send_wallet_update', 'message': expected_payload_message_content}
        )
    # ... (other UserWalletMethodTest tests like zero/negative, insufficient balance, atomicity)


class WalletAPITest(APITestCase):
    # ... (existing WalletAPITest tests) ...
    pass


# Import consumer for testing
from .consumers import WalletConsumer
# from channels.testing import WebsocketCommunicator # More involved, using simpler mocks for now

class WalletConsumerTest(TestCase): # Using TestCase, can use APITestCase if HTTP client needed
    async def setup_consumer(self, user=None):
        consumer = WalletConsumer()
        consumer.scope = {'user': user}
        consumer.channel_layer = MagicMock()
        consumer.channel_name = 'testwalletchannel'
        consumer.send = MagicMock(wraps=consumer.send)
        consumer.close = MagicMock(wraps=consumer.close)
        consumer.accept = MagicMock(wraps=consumer.accept)
        consumer.channel_layer.group_add = MagicMock(wraps=consumer.channel_layer.group_add)
        consumer.channel_layer.group_discard = MagicMock(wraps=consumer.channel_layer.group_discard)
        return consumer

    async def test_wallet_consumer_connect_authenticated(self):
        user = User(username='auth_walletconsumer_user', id=101)
        user.is_authenticated = True
        consumer = await self.setup_consumer(user=user)
        await consumer.connect()
        consumer.channel_layer.group_add.assert_called_once_with(f"user_{user.id}_wallet", 'testwalletchannel')
        consumer.accept.assert_called_once()
        consumer.close.assert_not_called()

    async def test_wallet_consumer_connect_unauthenticated(self):
        user = User(username='anon_walletconsumer_user', id=102)
        user.is_authenticated = False
        consumer = await self.setup_consumer(user=user)
        await consumer.connect()
        consumer.channel_layer.group_add.assert_not_called()
        consumer.accept.assert_not_called()
        consumer.close.assert_called_once()

    async def test_wallet_consumer_disconnect(self):
        user = User(username='auth_walletconsumer_user_dc', id=103)
        user.is_authenticated = True
        consumer = await self.setup_consumer(user=user)
        await consumer.connect()
        await consumer.disconnect("close_code_example")
        consumer.channel_layer.group_discard.assert_called_once_with(f"user_{user.id}_wallet", 'testwalletchannel')

    async def test_wallet_consumer_send_wallet_update_handler(self):
        user = User(username='auth_walletconsumer_send', id=104)
        user.is_authenticated = True
        consumer = await self.setup_consumer(user=user)
        event_message_content = {'balance': '123.45', 'description': 'Test update'}
        event = {'message': event_message_content}
        consumer.send = MagicMock() # Simple mock for send
        await consumer.send_wallet_update(event)
        consumer.send.assert_called_once_with(text_data=json.dumps(event_message_content))
