from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from .models import ArbitrageTradeAttempt, TradeOrderLeg
from unittest.mock import patch, MagicMock, PropertyMock
import uuid
import decimal
from django.test import override_settings
import time
from django.conf import settings
import json

from .consumers import TradeStatusConsumer # For consumer tests
from .signals import serialize_trade_attempt, serialize_trade_leg # For signal tests
from .trading_service import TradeExecutionService, EXCHANGE_RULES_PLACEHOLDER # For service tests
from exchange_clients.base_client import ExchangeAPIError # For service tests
from wallet_management.models import UserWallet # For service tests
from key_management.models import UserAPIKey # For service tests


class TradeExecutionServiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='tradetestuser_svc', password='password123', email='tradesvc@example.com')
        cls.wallet = UserWallet.objects.get(user=cls.user)
        cls.wallet.balance = decimal.Decimal('1000.00')
        cls.wallet.save()

        if not settings.SECRET_KEY:
            settings.SECRET_KEY = 'test_secret_key_for_trade_svc_tests'

        cls.binance_api_key_instance = UserAPIKey.objects.create(
            user=cls.user, exchange_name="Binance", api_key="test_binance_key_svc"
        )
        cls.binance_api_key_instance.api_secret = "test_binance_secret_svc"
        cls.binance_api_key_instance.save()

        cls.mock_opportunity_data_binance = {
            'exchange': 'Binance', 'path': ['BTCUSDT', 'ETHBTC', 'ETHUSDT'],
            'coins': ['USDT', 'BTC', 'ETH'], 'asset_sequence': ['USDT', 'BTC', 'ETH', 'USDT'],
            'rates': ['30000', '0.07', '2150'], 'profit': "0.23809403", 'profit_percent': 2.3809403,
            'actions_for_service': ['BUY', 'BUY', 'SELL'], 'base_coin_for_service': 'USDT'
        }
        EXCHANGE_RULES_PLACEHOLDER['Binance']['BTCUSDT'] = {"base_precision": 8, "quote_precision": 2, "min_qty": decimal.Decimal("0.00001"), "min_notional": decimal.Decimal("1.0")}
        EXCHANGE_RULES_PLACEHOLDER['Binance']['ETHBTC'] = {"base_precision": 8, "quote_precision": 8, "min_qty": decimal.Decimal("0.0001"), "min_notional": decimal.Decimal("0.00001")}
        EXCHANGE_RULES_PLACEHOLDER['Binance']['ETHUSDT'] = {"base_precision": 8, "quote_precision": 2, "min_qty": decimal.Decimal("0.0001"), "min_notional": decimal.Decimal("1.0")}

    def setUp(self):
        self.initial_wallet_balance = UserWallet.objects.get(user=self.user).balance
        # Instantiate service for each test method to ensure client is patched correctly per test
        self.service = TradeExecutionService(
            user=self.user,
            user_api_key_instance=self.binance_api_key_instance,
            opportunity_data=self.mock_opportunity_data_binance,
            start_amount_str="10.0"
        )
        # Mock the client on the service instance for depth check tests
        self.service.client = MagicMock()


    def test_check_order_book_depth_sufficient_buy(self):
        self.service.client.get_order_book_depth.return_value = {
            'asks': [
                [decimal.Decimal('30000'), decimal.Decimal('0.5')],
                [decimal.Decimal('30001'), decimal.Decimal('1.0')] # Total 1.5
            ], 'bids': []
        }
        required_qty = decimal.Decimal('0.8')
        price_limit = decimal.Decimal('30002') # Well above asks
        self.assertTrue(self.service._check_order_book_depth('BTCUSDT', 'BUY', required_qty, price_limit))

    def test_check_order_book_depth_insufficient_buy(self):
        self.service.client.get_order_book_depth.return_value = {
            'asks': [[decimal.Decimal('30000'), decimal.Decimal('0.1')]], 'bids': []
        }
        required_qty = decimal.Decimal('0.5')
        self.assertFalse(self.service._check_order_book_depth('BTCUSDT', 'BUY', required_qty))

    def test_check_order_book_depth_sufficient_sell(self):
        self.service.client.get_order_book_depth.return_value = {
            'bids': [
                [decimal.Decimal('29999'), decimal.Decimal('0.5')],
                [decimal.Decimal('29998'), decimal.Decimal('1.0')] # Total 1.5
            ], 'asks': []
        }
        required_qty = decimal.Decimal('1.2')
        price_limit = decimal.Decimal('29997') # Well below bids
        self.assertTrue(self.service._check_order_book_depth('BTCUSDT', 'SELL', required_qty, price_limit))

    def test_check_order_book_depth_price_limit_buy_fail(self):
        self.service.client.get_order_book_depth.return_value = {
            'asks': [[decimal.Decimal('30005'), decimal.Decimal('1.0')]], 'bids': [] # Price is above limit
        }
        required_qty = decimal.Decimal('0.5')
        price_limit = decimal.Decimal('30000') # Max price to pay
        # The check allows for 2% slippage, 30000 * 1.02 = 30600. So 30005 should pass.
        # If strict limit: self.assertFalse(...)
        # Let's test the strict interpretation first as per prompt, then adjust if needed.
        # Prompt example: if required_price_limit and price_level > required_price_limit * decimal.Decimal("1.02")
        # So, if price_level (30005) > price_limit (30000 * 1.02 = 30600) -> this is false, so it continues.
        # This means it should pass based on current slippage logic if qty is enough.
        self.assertTrue(self.service._check_order_book_depth('BTCUSDT', 'BUY', required_qty, price_limit))

        # Test if price is beyond slippage
        self.service.client.get_order_book_depth.return_value = {
            'asks': [[decimal.Decimal('30601'), decimal.Decimal('1.0')]], 'bids': []
        }
        self.assertFalse(self.service._check_order_book_depth('BTCUSDT', 'BUY', required_qty, price_limit))


    def test_check_order_book_depth_empty_book(self):
        self.service.client.get_order_book_depth.return_value = {'asks': [], 'bids': []}
        self.assertFalse(self.service._check_order_book_depth('BTCUSDT', 'BUY', decimal.Decimal('0.1')))

    def test_check_order_book_depth_api_error(self):
        self.service.client.get_order_book_depth.side_effect = ExchangeAPIError(500, "Service unavailable")
        self.assertFalse(self.service._check_order_book_depth('BTCUSDT', 'BUY', decimal.Decimal('0.1')))

    # ... (other service tests e.g. for commission, leg failure, etc.) ...
    # Example of a full run test with depth check mocked
    @patch.object(TradeExecutionService, '_check_order_book_depth', return_value=True) # Assume depth check passes
    @patch('trading_engine.trading_service.BinanceClient.create_market_order') # Mock actual order
    def test_run_with_successful_depth_check(self, mock_create_market_order, mock_depth_check):
        # Simplified mock for order responses
        mock_create_market_order.return_value = {"orderId": "mock_order", "status": "FILLED", "executedQty": "1", "fills": [{"price":"1", "qty":"1"}]}

        # Initial wallet balance for commission check
        self.wallet.balance = decimal.Decimal('100.00') # Ensure enough for commission later
        self.wallet.save()
        self.initial_wallet_balance = self.wallet.balance


        profitable_opportunity = self.mock_opportunity_data_binance.copy()
        profitable_opportunity['rates'] = ['10', '1', '1.1'] # 10 USDT -> 1 C_A -> 1 C_B -> 1.1 USDT (profit 0.1)
        profitable_opportunity['profit'] = "0.1"
        profitable_opportunity['profit_percent'] = 1.0

        # Mock quantities from _calculate_and_validate_leg_details to match rates simply
        # Leg 1: BUY C_A with USDT. 10 USDT / 10 (USDT/C_A) = 1 C_A
        # Leg 2: BUY C_B with C_A.  1 C_A / 1 (C_A/C_B) = 1 C_B
        # Leg 3: SELL C_B for USDT. 1 C_B * 1.1 (USDT/C_B) = 1.1 USDT

        # We need to mock _calculate_and_validate_leg_details or make its logic very predictable
        # For this test, let's assume calc_and_validate returns values that pass rules
        # and the output quantity matches the input for simplicity in mocking create_market_order

        def mock_calc_side_effect(leg_index, current_input_amount, current_input_asset_symbol):
            pair = profitable_opportunity['path'][leg_index]
            side = profitable_opportunity['actions_for_service'][leg_index]
            rate = decimal.Decimal(profitable_opportunity['rates'][leg_index])
            qty = decimal.Decimal('0')
            next_asset = profitable_opportunity['asset_sequence'][leg_index+1]
            if side == 'BUY': qty = current_input_amount / rate
            else: qty = current_input_amount
            return pair, side, qty, rate, next_asset

        with patch.object(self.service, '_calculate_and_validate_leg_details', side_effect=mock_calc_side_effect):
            trade_attempt = self.service.run()

        self.assertEqual(trade_attempt.status, 'completed')
        mock_depth_check.assert_called() # Ensure depth check was called for each leg
        self.assertEqual(mock_depth_check.call_count, 3)
        self.assertEqual(mock_create_market_order.call_count, 3)

        expected_profit = decimal.Decimal("0.1")
        self.assertAlmostEqual(trade_attempt.actual_profit, expected_profit, places=8)
        expected_commission = (expected_profit * decimal.Decimal('0.10')).quantize(decimal.Decimal('0.00000001'), rounding=decimal.ROUND_DOWN)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, self.initial_wallet_balance - expected_commission)


@override_settings(REST_FRAMEWORK={
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'user': '100/day', 'trade_execute': '2/minute'}
})
class TradingAPIEndpointsTest(APITestCase):
    # ... (existing API tests) ...
    pass # Keep existing tests


class TradeStatusConsumerTest(TestCase):
    # ... (existing consumer tests) ...
    pass

class TradingSignalTest(TestCase):
    # ... (existing signal tests) ...
    pass
