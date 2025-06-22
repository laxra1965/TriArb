import requests
import decimal
from .models import TrackedExchangePair
from arbitrage_scanner.scanner_utils import standardize_symbol_backend as shared_standardize_symbol
from django.core.cache import cache # Import Django's cache
from django.utils import timezone # For setting last_volume_update
# import datetime # Not strictly needed if VOLUME_CACHE_TIMEOUT_SECONDS is just int
import logging # Added for logging

logger = logging.getLogger(__name__) # Get a logger instance for this module

# Cache timeout for volume data (e.g., 15 minutes)
VOLUME_CACHE_TIMEOUT_SECONDS = 15 * 60

def get_binance_pair_volume_and_price(pair_instance: TrackedExchangePair):
    """Fetches 24h volume and last price for a specific Binance pair and updates the instance. Uses cache."""
    if pair_instance.exchange_name != 'Binance':
        return False

    cache_key = f"binance_volume_price_{pair_instance.raw_exchange_symbol}"
    cached_data = cache.get(cache_key)

    if cached_data:
        pair_instance.volume_24h_base = cached_data.get('volume_24h_base')
        pair_instance.volume_24h_quote = cached_data.get('volume_24h_quote')
        pair_instance.last_price = cached_data.get('last_price')
        pair_instance.last_volume_update = cached_data.get('last_volume_update')
            logger.debug(f"Using cached volume/price for Binance {pair_instance.raw_exchange_symbol}")
        return True # Data loaded from cache

    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair_instance.raw_exchange_symbol}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        last_price = decimal.Decimal(data.get('lastPrice', '0'))
        volume_base = decimal.Decimal(data.get('volume', '0'))
        volume_quote = decimal.Decimal(data.get('quoteVolume', '0'))

        current_time = timezone.now()
        pair_instance.last_price = last_price
        pair_instance.volume_24h_base = volume_base
        pair_instance.volume_24h_quote = volume_quote
        pair_instance.last_volume_update = current_time
        # pair_instance.save(update_fields=['last_price', 'volume_24h_base', 'volume_24h_quote', 'last_volume_update']) # Save to DB too

        cache_data = {
            'volume_24h_base': volume_base,
            'volume_24h_quote': volume_quote,
            'last_price': last_price,
            'last_volume_update': current_time
        }
        cache.set(cache_key, cache_data, timeout=VOLUME_CACHE_TIMEOUT_SECONDS)
            logger.debug(f"Fetched and cached volume/price for Binance {pair_instance.raw_exchange_symbol}")
        return True
    except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching 24hr ticker for Binance {pair_instance.raw_exchange_symbol}: {e}", exc_info=True)
        return False
    except Exception as e:
            logger.error(f"Error processing 24hr ticker data for Binance {pair_instance.raw_exchange_symbol}: {e}", exc_info=True)
        return False


def get_bybit_pair_volume_and_price(pair_instance: TrackedExchangePair):
    """Fetches 24h volume and last price for a specific Bybit spot pair and updates the instance. Uses cache."""
    if pair_instance.exchange_name != 'Bybit':
        return False

    cache_key = f"bybit_volume_price_{pair_instance.raw_exchange_symbol}"
    cached_data = cache.get(cache_key)
    if cached_data:
        pair_instance.volume_24h_base = cached_data.get('volume_24h_base')
        pair_instance.volume_24h_quote = cached_data.get('volume_24h_quote')
        pair_instance.last_price = cached_data.get('last_price')
        pair_instance.last_volume_update = cached_data.get('last_volume_update')
            logger.debug(f"Using cached volume/price for Bybit {pair_instance.raw_exchange_symbol}")
        return True

    url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={pair_instance.raw_exchange_symbol}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get('retCode') == 0 and data.get('result') and isinstance(data['result'].get('list'), list) and len(data['result']['list']) > 0:
            ticker_data = data['result']['list'][0]
            last_price = decimal.Decimal(ticker_data.get('lastPrice', '0'))
            volume_base = decimal.Decimal(ticker_data.get('volume24h', '0'))
            volume_quote = decimal.Decimal(ticker_data.get('turnover24h', '0'))

            current_time = timezone.now()
            pair_instance.last_price = last_price
            pair_instance.volume_24h_base = volume_base
            pair_instance.volume_24h_quote = volume_quote
            pair_instance.last_volume_update = current_time
            # pair_instance.save(update_fields=['last_price', 'volume_24h_base', 'volume_24h_quote', 'last_volume_update'])

            cache_data = {
                'volume_24h_base': volume_base,
                'volume_24h_quote': volume_quote,
                'last_price': last_price,
                'last_volume_update': current_time
            }
            cache.set(cache_key, cache_data, timeout=VOLUME_CACHE_TIMEOUT_SECONDS)
            logger.debug(f"Fetched and cached volume/price for Bybit {pair_instance.raw_exchange_symbol}")
            return True
        else:
            logger.warning(f"Error or empty data in Bybit 24hr ticker response for {pair_instance.raw_exchange_symbol}: {data.get('retMsg', 'Unknown error')}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching 24hr ticker for Bybit {pair_instance.raw_exchange_symbol}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Error processing 24hr ticker data for Bybit {pair_instance.raw_exchange_symbol}: {e}", exc_info=True)
        return False

def update_binance_pairs():
    """Fetches all spot trading pairs from Binance and updates the TrackedExchangePair model."""
    url = "https://api.binance.com/api/v3/exchangeInfo"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        found_symbols = set()
        for pair_info in data.get('symbols', []):
            if pair_info.get('status') == 'TRADING' and 'SPOT' in pair_info.get('permissions', []):
                raw_symbol = pair_info['symbol']
                base_asset = pair_info['baseAsset']
                quote_asset = pair_info['quoteAsset']
                standardized_symbol = shared_standardize_symbol(raw_symbol, 'Binance')

                precision_details = {
                    'baseAssetPrecision': pair_info.get('baseAssetPrecision'),
                    'quoteAssetPrecision': pair_info.get('quotePrecision'),
                    'filters': pair_info.get('filters', [])
                }

                obj, created = TrackedExchangePair.objects.update_or_create(
                    exchange_name='Binance',
                    symbol=standardized_symbol,
                    defaults={
                        'raw_exchange_symbol': raw_symbol,
                        'base_asset': base_asset,
                        'quote_asset': quote_asset,
                        'precision_rules_json': precision_details,
                        'is_active_for_scan': True
                    }
                )
                found_symbols.add(standardized_symbol)

        TrackedExchangePair.objects.filter(exchange_name='Binance').exclude(symbol__in=found_symbols).update(is_active_for_scan=False)
        logger.info(f"Binance pairs updated. Found {len(found_symbols)} active pairs.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Binance pairs: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error processing Binance pair data: {e}", exc_info=True)

def update_bybit_pairs():
    """Fetches all spot trading pairs from Bybit and updates the TrackedExchangePair model."""
    url = "https://api.bybit.com/v5/market/instruments-info?category=spot"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        found_symbols = set()
        if data.get('retCode') == 0 and data.get('result') and isinstance(data['result'].get('list'), list):
            for pair_info in data['result']['list']:
                if pair_info.get('status') == 'Trading':
                    raw_symbol = pair_info['symbol']
                    base_asset = pair_info['baseCoin']
                    quote_asset = pair_info['quoteCoin']
                    standardized_symbol = shared_standardize_symbol(raw_symbol, 'Bybit')

                    precision_details = {
                        'basePrecision': pair_info.get('priceFilter', {}).get('tickSize'),
                        'quotePrecision': pair_info.get('lotSizeFilter', {}).get('qtyStep'),
                        'leverageFilter': pair_info.get('leverageFilter'),
                        'priceFilter': pair_info.get('priceFilter'),
                        'lotSizeFilter': pair_info.get('lotSizeFilter'),
                    }

                    obj, created = TrackedExchangePair.objects.update_or_create(
                        exchange_name='Bybit',
                        symbol=standardized_symbol,
                        defaults={
                            'raw_exchange_symbol': raw_symbol,
                            'base_asset': base_asset,
                            'quote_asset': quote_asset,
                            'precision_rules_json': precision_details,
                            'is_active_for_scan': True
                        }
                    )
                    found_symbols.add(standardized_symbol)

        TrackedExchangePair.objects.filter(exchange_name='Bybit').exclude(symbol__in=found_symbols).update(is_active_for_scan=False)
        logger.info(f"Bybit pairs updated. Found {len(found_symbols)} active pairs.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Bybit pairs: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error processing Bybit pair data: {e}", exc_info=True)

def update_all_exchange_pairs():
    update_binance_pairs()
    update_bybit_pairs()
    # TODO: Add calls to other exchange pair updaters here
    logger.info("All exchange pair updates attempted.")
