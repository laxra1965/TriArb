from django.test import TestCase
from unittest.mock import patch, MagicMock, PropertyMock, ANY
from .scanner_service import scan_for_arbitrage
from .arbitrage_logic import find_triangular_arbitrage_opportunities
from .scanner_utils import fetch_specific_tickers_data, fetch_exchange_ticker_data # Import for direct test
from market_data.models import TrackedExchangePair # For creating test instances
import decimal
import json # For mocking requests.get().json()

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from wallet_management.models import UserWallet
from django.test import override_settings
import time


class ArbitrageScannerServiceTest(TestCase):
    # ... (existing service tests) ...
    @patch('arbitrage_scanner.scanner_service.find_triangular_arbitrage_opportunities')
    @patch('arbitrage_scanner.scanner_service.fetch_exchange_ticker_data') # V1 fetcher
    @patch('arbitrage_scanner.scanner_service.fetch_specific_tickers_data') # V2 fetcher
    @patch('arbitrage_scanner.scanner_service.get_liquid_pairs')
    def test_scan_for_arbitrage_v2_flow(self, mock_get_liquid_pairs, mock_fetch_specific_tickers,
                                       mock_fetch_exchange_tickers_v1, mock_find_opportunities):
        """Test the V2 logic path in scan_for_arbitrage service."""
        exchange_name = "Binance"
        mock_user_api_instances = {} # Empty for this test, assuming public access for specific tickers

        # 1. Mock get_liquid_pairs
        mock_pair_1 = MagicMock(spec=TrackedExchangePair)
        mock_pair_1.symbol = "BTCUSDT"
        mock_pair_1.raw_exchange_symbol = "BTCUSDT"
        mock_pair_1.exchange_name = exchange_name

        mock_pair_2 = MagicMock(spec=TrackedExchangePair)
        mock_pair_2.symbol = "ETHUSDT"
        mock_pair_2.raw_exchange_symbol = "ETHUSDT"
        mock_pair_2.exchange_name = exchange_name

        mock_liquid_pairs_qs = MagicMock()
        mock_liquid_pairs_qs.exists.return_value = True
        # Make it iterable for fetch_specific_tickers_data if it expects an iterable
        mock_liquid_pairs_qs.__iter__.return_value = [mock_pair_1, mock_pair_2]
        # Or if it's directly used as a queryset:
        # mock_liquid_pairs_qs.filter.return_value = mock_liquid_pairs_qs
        # mock_liquid_pairs_qs.all.return_value = [mock_pair_1, mock_pair_2]


        mock_get_liquid_pairs.return_value = mock_liquid_pairs_qs

        # 2. Mock fetch_specific_tickers_data
        mock_specific_tickers_map = {
            "BTCUSDT": {"bidPrice": decimal.Decimal("30000"), "askPrice": decimal.Decimal("30001")},
            "ETHUSDT": {"bidPrice": decimal.Decimal("2000"), "askPrice": decimal.Decimal("2001")}
        }
        mock_fetch_specific_tickers.return_value = mock_specific_tickers_map

        # 3. Mock find_triangular_arbitrage_opportunities
        mock_opportunities = [{"profit_percent": 1.0, "path": ["BTCUSDT", "ETHBTC", "ETHUSDT"]}]
        mock_find_opportunities.return_value = mock_opportunities

        # Call the service with version='v2'
        results = scan_for_arbitrage(
            selected_exchanges=[exchange_name],
            version="v2",
            user_api_key_instances=mock_user_api_instances
        )

        mock_get_liquid_pairs.assert_called_once_with(exchange_name=exchange_name)
        # The argument to fetch_specific_tickers_data should be the queryset/list of TrackedExchangePair objects
        mock_fetch_specific_tickers.assert_called_once_with(
            exchange_name,
            mock_liquid_pairs_qs, # Pass the queryset itself
            user_api_key_instance=None
        )
        mock_find_opportunities.assert_called_once_with(
            mock_specific_tickers_map,
            base_coin="USDT",
            start_amount=decimal.Decimal("10.0")
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['profit_percent'], 1.0)
        self.assertEqual(results[0]['scanner_version'], 'v2')
        # V1 fetcher should not be called
        mock_fetch_exchange_tickers_v1.assert_not_called()


class FetchSpecificTickersDataTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create TrackedExchangePair instances for testing
        cls.binance_btc_usdt = TrackedExchangePair.objects.create(exchange_name='Binance', symbol='BTCUSDT', raw_exchange_symbol='BTCUSDT', base_asset='BTC', quote_asset='USDT', is_active_for_scan=True)
        cls.binance_eth_usdt = TrackedExchangePair.objects.create(exchange_name='Binance', symbol='ETHUSDT', raw_exchange_symbol='ETHUSDT', base_asset='ETH', quote_asset='USDT', is_active_for_scan=True)
        cls.bybit_btc_usdt = TrackedExchangePair.objects.create(exchange_name='Bybit', symbol='BTCUSDT', raw_exchange_symbol='BTCUSDT', base_asset='BTC', quote_asset='USDT', is_active_for_scan=True)

    @patch('arbitrage_scanner.scanner_utils.requests.get')
    def test_fetch_specific_for_binance_multi_symbol(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'symbol': 'BTCUSDT', 'bidPrice': '30000.00', 'askPrice': '30001.00'},
            {'symbol': 'ETHUSDT', 'bidPrice': '2000.00', 'askPrice': '2001.00'}
        ]
        mock_requests_get.return_value = mock_response

        pairs_to_fetch = TrackedExchangePair.objects.filter(exchange_name='Binance')
        result_map = fetch_specific_tickers_data('Binance', pairs_to_fetch)

        expected_symbols_json = json.dumps(["BTCUSDT", "ETHUSDT"]) # Order might vary, but content matters
        # Check if 'symbols' parameter was correctly formatted in the call
        called_url_params = mock_requests_get.call_args[1]['params']
        self.assertIn('symbols', called_url_params)
        self.assertEqual(json.loads(called_url_params['symbols']), ["BTCUSDT", "ETHUSDT"]) # Check content

        self.assertEqual(len(result_map), 2)
        self.assertEqual(result_map['BTCUSDT']['bidPrice'], decimal.Decimal('30000.00'))
        self.assertEqual(result_map['ETHUSDT']['askPrice'], decimal.Decimal('2001.00'))

    @patch('arbitrage_scanner.scanner_utils.requests.get')
    def test_fetch_specific_for_binance_single_symbol(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Binance returns a single dict if one symbol is queried via `symbol=` not `symbols=`
        mock_response.json.return_value = {'symbol': 'BTCUSDT', 'bidPrice': '30000.00', 'askPrice': '30001.00'}
        mock_requests_get.return_value = mock_response

        pairs_to_fetch = TrackedExchangePair.objects.filter(exchange_name='Binance', symbol='BTCUSDT')
        result_map = fetch_specific_tickers_data('Binance', pairs_to_fetch)

        mock_requests_get.assert_called_once_with(
            "https://api.binance.com/api/v3/ticker/bookTicker", # From config
            params={'symbol': 'BTCUSDT'},
            timeout=10
        )
        self.assertEqual(len(result_map), 1)
        self.assertEqual(result_map['BTCUSDT']['bidPrice'], decimal.Decimal('30000.00'))


    @patch('arbitrage_scanner.scanner_utils.fetch_exchange_ticker_data') # Mock the V1 style fetcher
    def test_fetch_specific_for_bybit(self, mock_v1_fetch_exchange_ticker_data):
        # Simulate V1 fetcher returning all Bybit tickers (standardized keys)
        mock_v1_fetch_exchange_ticker_data.return_value = {
            'BTCUSDT': {'bidPrice': decimal.Decimal('30005.00'), 'askPrice': decimal.Decimal('30006.00')},
            'ETHUSDT': {'bidPrice': decimal.Decimal('2002.00'), 'askPrice': decimal.Decimal('2003.00')}
        }

        pairs_to_fetch = TrackedExchangePair.objects.filter(exchange_name='Bybit', symbol='BTCUSDT')
        result_map = fetch_specific_tickers_data('Bybit', pairs_to_fetch)

        mock_v1_fetch_exchange_ticker_data.assert_called_once_with('Bybit', user_api_key_instance_map=None)
        self.assertEqual(len(result_map), 1)
        self.assertIn('BTCUSDT', result_map)
        self.assertEqual(result_map['BTCUSDT']['bidPrice'], decimal.Decimal('30005.00'))

    def test_fetch_specific_empty_list(self):
        result = fetch_specific_tickers_data('Binance', [])
        self.assertEqual(result, {})


# ... (ArbitrageOpportunitiesAPITest class from previous step, ensure it uses override_settings correctly if it's separate) ...
# For brevity, the ArbitrageOpportunitiesAPITest is assumed to be correctly defined above or in a separate execution.
# The override_settings for ArbitrageOpportunitiesAPITest should be specific to that class.
# If merging, ensure @override_settings is at the class level where it's needed.

# Re-pasting ArbitrageOpportunitiesAPITest with its own override_settings to ensure clarity
@override_settings(REST_FRAMEWORK={
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'user': '100/day', 'opportunity_scan': '2/minute'}
})
class ArbitrageOpportunitiesAPITest(APITestCase):
    # ... (rest of the ArbitrageOpportunitiesAPITest class as defined before) ...
    @classmethod
    def setUpTestData(cls):
        cls.user_password = "scanner_api_password"
        cls.user = User.objects.create_user(username='testuser_scanner_api', email='scannerapi@example.com', password=cls.user_password)
        cls.wallet = UserWallet.objects.get(user=cls.user)
        cls.original_min_balance = getattr(settings, 'MINIMUM_SCANNER_ACCESS_BALANCE', decimal.Decimal('1.0'))
        settings.MINIMUM_SCANNER_ACCESS_BALANCE = decimal.Decimal('5.0')

    @classmethod
    def tearDownClass(cls):
        settings.MINIMUM_SCANNER_ACCESS_BALANCE = cls.original_min_balance
        super().tearDownClass()

    def setUp(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')
        self.opportunities_url = reverse("arbitrage_scanner:arbitrage_opportunities")

    def set_wallet_balance(self, balance_str):
        self.wallet.balance = decimal.Decimal(balance_str)
        self.wallet.save()

    @patch('arbitrage_scanner.views.scan_for_arbitrage')
    def test_get_opportunities_sufficient_balance(self, mock_scan_service):
        self.set_wallet_balance("10.00")
        mock_scan_service.return_value = [{"exchange": "Test", "profit_percent": 1.5}]
        response = self.client.get(self.opportunities_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_scan_service.assert_called_once()

    # ... (other tests from ArbitrageOpportunitiesAPITest) ...
    def test_get_opportunities_unauthenticated(self): # Example of an existing test
        self.client.credentials()
        response = self.client.get(self.opportunities_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('arbitrage_scanner.views.scan_for_arbitrage')
    def test_opportunity_scan_throttling(self, mock_scan_service): # From previous step
        self.set_wallet_balance("10.00")
        mock_scan_service.return_value = []
        for i in range(2):
            response = self.client.get(self.opportunities_url, format='json')
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        response = self.client.get(self.opportunities_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
