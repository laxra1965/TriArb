# arbitrage_platform/market_data/filters.py
from django.conf import settings
from .models import TrackedExchangePair
from django.db.models import Q
import decimal

def get_liquid_pairs(exchange_name=None):
    """
    Filters TrackedExchangePair objects based on liquidity criteria defined in settings
    and their 'is_active_for_scan' status.

    :param exchange_name: Optional specific exchange name to filter by.
    :return: QuerySet of TrackedExchangePair instances.
    """

    # Start with active pairs
    queryset = TrackedExchangePair.objects.filter(is_active_for_scan=True)

    if exchange_name:
        queryset = queryset.filter(exchange_name=exchange_name)

    # 1. Filter by Volume Threshold
    # Assumes volume_24h_quote is in a common currency like USDT or has been normalized.
    # For this example, we use V2_SCANNER_DEFAULT_VOLUME_THRESHOLD_USDT directly.
    # A more advanced setup might convert all volumes to a reference currency (e.g., USDT)
    # before applying the threshold, if quote_asset varies widely and threshold is in USDT.
    volume_threshold = getattr(settings, 'V2_SCANNER_DEFAULT_VOLUME_THRESHOLD_USDT', decimal.Decimal('0.0'))
    if volume_threshold > decimal.Decimal('0.0'):
        # Ensure volume_24h_quote is not None before comparison
        queryset = queryset.filter(volume_24h_quote__isnull=False, volume_24h_quote__gte=volume_threshold)

    # 2. Filter by Preferred Quote Assets
    preferred_quote_assets = getattr(settings, 'V2_SCANNER_DEFAULT_QUOTE_ASSETS', [])
    if preferred_quote_assets:
        # Ensure quote_asset is not None and in the list
        queryset = queryset.filter(quote_asset__isnull=False, quote_asset__in=preferred_quote_assets)

    # 3. Filter by Globally Excluded Pairs
    # V2_SCANNER_GLOBALLY_EXCLUDED_PAIRS is expected to be a list of strings like 'ExchangeName_StandardizedSymbol'
    # e.g., ['Binance_BTCUSDT', 'Bybit_ETHUSDT']
    globally_excluded_pairs_setting = getattr(settings, 'V2_SCANNER_GLOBALLY_EXCLUDED_PAIRS', [])
    if globally_excluded_pairs_setting:
        # We need to construct Q objects to exclude multiple exchange-symbol combinations
        exclusion_conditions = Q()
        for excluded_item in globally_excluded_pairs_setting:
            try:
                exc_name, sym = excluded_item.split('_', 1)
                exclusion_conditions |= Q(exchange_name=exc_name, symbol=sym)
            except ValueError:
                # Log malformed excluded pair string
                print(f"Warning: Malformed entry in V2_SCANNER_GLOBALLY_EXCLUDED_PAIRS: {excluded_item}")

        if exclusion_conditions: # If any valid exclusion conditions were built
            queryset = queryset.exclude(exclusion_conditions)

    # Ensure necessary data for scanning is present (e.g., last_price)
    # This might be more of a check during the scan itself, but can pre-filter.
    queryset = queryset.filter(last_price__isnull=False, last_price__gt=decimal.Decimal('0'))


    # Logging the count of pairs after filtering
    # print(f"Liquidity filter for exchange '{exchange_name or 'All'}': {queryset.count()} pairs passed.")

    return queryset

# Example Usage (for testing this function in isolation):
# if __name__ == '__main__':
#     # Configure Django settings if running standalone for testing
#     # import os, django
#     # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arbitrage_platform.settings')
#     # django.setup()
#
#     # Example: Get liquid pairs for Binance
#     liquid_binance_pairs = get_liquid_pairs(exchange_name='Binance')
#     print(f"Found {liquid_binance_pairs.count()} liquid Binance pairs.")
#     for pair in liquid_binance_pairs:
#         print(f" - {pair.symbol}, Volume (Quote): {pair.volume_24h_quote} {pair.quote_asset}")
#
#     # Example: Get all liquid pairs across configured exchanges
#     all_liquid_pairs = get_liquid_pairs()
#     print(f"Found {all_liquid_pairs.count()} liquid pairs across all exchanges.")
#     for pair in all_liquid_pairs:
#         print(f" - {pair.exchange_name} {pair.symbol}, Volume (Quote): {pair.volume_24h_quote} {pair.quote_asset}")
