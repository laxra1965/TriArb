from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from .models import TrackedExchangePair
from .filters import get_liquid_pairs
import decimal
from unittest.mock import patch, MagicMock # For Celery task tests
from django.utils import timezone # For mocking datetime
import datetime # For direct use if needed

class GetLiquidPairsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        TrackedExchangePair.objects.create(
            exchange_name='Binance', symbol='BTCUSDT', raw_exchange_symbol='BTCUSDT',
            base_asset='BTC', quote_asset='USDT', is_active_for_scan=True,
            volume_24h_quote=decimal.Decimal('100000.00'), last_price=decimal.Decimal('30000.00')
        )
        TrackedExchangePair.objects.create(
            exchange_name='Binance', symbol='ETHUSDT', raw_exchange_symbol='ETHUSDT',
            base_asset='ETH', quote_asset='USDT', is_active_for_scan=True,
            volume_24h_quote=decimal.Decimal('80000.00'), last_price=decimal.Decimal('2000.00')
        )
        TrackedExchangePair.objects.create(
            exchange_name='Binance', symbol='LTCUSDT', raw_exchange_symbol='LTCUSDT',
            base_asset='LTC', quote_asset='USDT', is_active_for_scan=True,
            volume_24h_quote=decimal.Decimal('10000.00'), last_price=decimal.Decimal('100.00')
        )
        TrackedExchangePair.objects.create(
            exchange_name='Binance', symbol='ADAEUR', raw_exchange_symbol='ADAEUR',
            base_asset='ADA', quote_asset='EUR', is_active_for_scan=True,
            volume_24h_quote=decimal.Decimal('60000.00'), last_price=decimal.Decimal('0.5')
        )
        TrackedExchangePair.objects.create(
            exchange_name='Binance', symbol='XRPUSDT', raw_exchange_symbol='XRPUSDT',
            base_asset='XRP', quote_asset='USDT', is_active_for_scan=False,
            volume_24h_quote=decimal.Decimal('200000.00'), last_price=decimal.Decimal('0.5')
        )
        TrackedExchangePair.objects.create(
            exchange_name='Binance', symbol='SOLUSDT', raw_exchange_symbol='SOLUSDT',
            base_asset='SOL', quote_asset='USDT', is_active_for_scan=True,
            volume_24h_quote=decimal.Decimal('90000.00'), last_price=None
        )
        TrackedExchangePair.objects.create(
            exchange_name='Bybit', symbol='BTCUSDT', raw_exchange_symbol='BTCUSDT',
            base_asset='BTC', quote_asset='USDT', is_active_for_scan=True,
            volume_24h_quote=decimal.Decimal('120000.00'), last_price=decimal.Decimal('30005.00')
        )
        TrackedExchangePair.objects.create(
            exchange_name='Binance', symbol='BNBUSDT', raw_exchange_symbol='BNBUSDT',
            base_asset='BNB', quote_asset='USDT', is_active_for_scan=True,
            volume_24h_quote=decimal.Decimal('75000.00'), last_price=decimal.Decimal('300.00')
        )

    # ... (existing tests for get_liquid_pairs) ...
    @override_settings(
        V2_SCANNER_DEFAULT_VOLUME_THRESHOLD_USDT=decimal.Decimal('50000.00'),
        V2_SCANNER_DEFAULT_QUOTE_ASSETS=['USDT', 'BTC'],
        V2_SCANNER_GLOBALLY_EXCLUDED_PAIRS=[]
    )
    def test_filter_by_activity_volume_quote_asset_and_price(self):
        liquid_pairs = get_liquid_pairs()
        self.assertEqual(liquid_pairs.count(), 3)
        # ... (more assertions from previous step)

    @override_settings(
        V2_SCANNER_DEFAULT_VOLUME_THRESHOLD_USDT=decimal.Decimal('1000.00'),
        V2_SCANNER_DEFAULT_QUOTE_ASSETS=['USDT'],
        V2_SCANNER_GLOBALLY_EXCLUDED_PAIRS=['Binance_ETHUSDT', 'Bybit_BTCUSDT']
    )
    def test_global_exclusion_filter(self):
        liquid_pairs = get_liquid_pairs()
        symbols = {f"{p.exchange_name}_{p.symbol}" for p in liquid_pairs}
        self.assertIn('Binance_BTCUSDT', symbols)
        self.assertIn('Binance_LTCUSDT', symbols)
        self.assertIn('Binance_BNBUSDT', symbols)
        self.assertNotIn('Binance_ETHUSDT', symbols)
        self.assertNotIn('Bybit_BTCUSDT', symbols)
        self.assertEqual(liquid_pairs.count(), 3)


class MarketDataCeleryTasksTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.binance_pair = TrackedExchangePair.objects.create(
            exchange_name='Binance', symbol='BTCUSDT', raw_exchange_symbol='BTCUSDT',
            base_asset='BTC', quote_asset='USDT', is_active_for_scan=True
        )
        cls.bybit_pair = TrackedExchangePair.objects.create(
            exchange_name='Bybit', symbol='ETHUSDT', raw_exchange_symbol='ETHUSDT',
            base_asset='ETH', quote_asset='USDT', is_active_for_scan=True
        )
        cls.inactive_pair = TrackedExchangePair.objects.create(
            exchange_name='Binance', symbol='LTCUSDT', raw_exchange_symbol='LTCUSDT',
            base_asset='LTC', quote_asset='USDT', is_active_for_scan=False # Inactive
        )

    @patch('market_data.tasks.update_all_exchange_pairs_util')
    def test_update_all_pairs_from_exchanges_task(self, mock_update_util):
        from .tasks import update_all_pairs_from_exchanges_task
        result = update_all_pairs_from_exchanges_task.run() # Using .run() for direct execution in test
        mock_update_util.assert_called_once()
        self.assertEqual(result, "All exchange pairs discovery process completed.")

    @patch('market_data.tasks.get_binance_pair_volume_and_price')
    @patch.object(TrackedExchangePair, 'save') # Mock save method of the model instance
    def test_update_single_pair_volume_task_binance_success(self, mock_pair_save, mock_get_volume):
        from .tasks import update_single_pair_volume_task

        # Simulate that get_binance_pair_volume_and_price successfully updates the instance
        def mock_volume_side_effect(pair_instance):
            pair_instance.last_volume_update = timezone.now() # Simulate update
            pair_instance.last_price = decimal.Decimal('31000')
            pair_instance.volume_24h_base = decimal.Decimal('1000')
            pair_instance.volume_24h_quote = decimal.Decimal('31000000')
            return True
        mock_get_volume.side_effect = mock_volume_side_effect

        result = update_single_pair_volume_task.run(self.binance_pair.id)

        mock_get_volume.assert_called_once_with(self.binance_pair)
        mock_pair_save.assert_called_once_with(update_fields=['last_price', 'volume_24h_base', 'volume_24h_quote', 'last_volume_update'])
        self.assertIn("Volume updated for BTCUSDT", result)

    @patch('market_data.tasks.get_bybit_pair_volume_and_price')
    @patch.object(TrackedExchangePair, 'save')
    def test_update_single_pair_volume_task_bybit_fetch_fail(self, mock_pair_save, mock_get_volume):
        from .tasks import update_single_pair_volume_task
        mock_get_volume.return_value = False # Simulate fetch failure

        result = update_single_pair_volume_task.run(self.bybit_pair.id)

        mock_get_volume.assert_called_once_with(self.bybit_pair)
        mock_pair_save.assert_not_called() # Save should not be called if fetch failed
        self.assertIn("Failed to update volume for ETHUSDT", result)

    def test_update_single_pair_volume_task_pair_not_found(self):
        from .tasks import update_single_pair_volume_task
        non_existent_id = 99999
        result = update_single_pair_volume_task.run(non_existent_id)
        self.assertIn(f"Pair ID {non_existent_id} not found.", result)

    @patch('market_data.tasks.get_binance_pair_volume_and_price', side_effect=Exception("Generic API Error"))
    @patch.object(TrackedExchangePair, 'save')
    def test_update_single_pair_volume_task_generic_exception(self, mock_pair_save, mock_get_volume):
        from .tasks import update_single_pair_volume_task
        result = update_single_pair_volume_task.run(self.binance_pair.id)
        mock_get_volume.assert_called_once()
        mock_pair_save.assert_not_called() # Save should not be called on exception before save
        self.assertIn(f"Error updating volume for pair ID {self.binance_pair.id}: Generic API Error", result)


    @patch('market_data.tasks.update_single_pair_volume_task.delay')
    @patch('market_data.tasks.time.sleep') # To prevent actual sleep
    def test_schedule_all_active_pair_volume_updates_task(self, mock_sleep, mock_delay_task):
        from .tasks import schedule_all_active_pair_volume_updates_task

        result = schedule_all_active_pair_volume_updates_task.run()

        # We have 2 active pairs: self.binance_pair, self.bybit_pair
        self.assertEqual(TrackedExchangePair.objects.filter(is_active_for_scan=True).count(), 2)
        self.assertEqual(mock_delay_task.call_count, 2)
        mock_delay_task.assert_any_call(self.binance_pair.id)
        mock_delay_task.assert_any_call(self.bybit_pair.id)

        # Check staggering (sleep called n-1 times, or n times depending on placement)
        # Current implementation sleeps after each .delay() call.
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(1) # Check if sleep was called with 1 second

        self.assertIn("Scheduled volume updates for 2 pairs.", result)
