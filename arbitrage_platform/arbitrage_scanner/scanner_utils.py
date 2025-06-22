# arbitrage_platform/arbitrage_scanner/scanner_utils.py
import requests
import decimal
import json # Added for Binance multi-symbol request
from .exchange_config import EXCHANGE_API_CONFIG, get_client_class
# from market_data.models import TrackedExchangePair # If needed for type hinting

def standardize_symbol_backend(symbol_str, exchange_name): # Keep existing function
    if not symbol_str: return None
    s = str(symbol_str).upper().replace('-', '').replace('_', '').replace('/', '').replace(':', '')
    if exchange_name == 'Kraken':
        if s.startswith('XBT'): s = s.replace('XBT', 'BTC')
        elif s.startswith('XDG'): s = s.replace('XDG', 'DOGE')
        if s.endswith('ZUSD'): s = s.replace('ZUSD', 'USD')
        elif s.endswith('ZEUR'): s = s.replace('ZEUR', 'EUR')
        if 'XXBT' in s: s = s.replace('XXBT', 'BTC')
    if exchange_name == 'Bitfinex':
        if s.startswith('T') and len(s) > 1: s = s[1:]
    if s.endswith("USD") and not s.endswith("USDT") and not s.endswith("USDC"):
        s = s[:-3] + "USDT"
    if s.endswith("USDTUSDT"): s = s[:-4]
    if s.endswith("EURUSDT") and len(s) > 7 : s = s.replace("EURUSDT","EUR")
    return s

def fetch_exchange_ticker_data(exchange_name, user_api_key_instance_map=None): # Keep existing function
    config = EXCHANGE_API_CONFIG.get(exchange_name)
    if not config:
        print(f"Error: Unknown exchange configured: {exchange_name}")
        return {}
    all_tickers_map = {}
    raw_data = None
    try:
        if config['type'] == 'client_or_public' and \
           user_api_key_instance_map and \
           exchange_name in user_api_key_instance_map and \
           config.get('client_class_ref') and \
           config.get('client_method_tickers'):
            client_class_str = config['client_class_ref']
            client_method_name = config['client_method_tickers']
            client_class = get_client_class(client_class_str)
            key_instance = user_api_key_instance_map[exchange_name]
            client = client_class(user_api_key_instance=key_instance)
            raw_data = getattr(client, client_method_name)()
        elif config.get('public_ticker_url'):
            response = requests.get(config['public_ticker_url'], timeout=10)
            response.raise_for_status()
            raw_data = response.json()
        elif config.get('url'):
            response = requests.get(config['url'], timeout=10)
            response.raise_for_status()
            raw_data = response.json()
        else:
            print(f"Error: No valid fetch method configured for {exchange_name}")
            return {}
        if not raw_data: return {}

        # Simplified parsing logic from before - this will be reused by fetch_specific_tickers_data for Bybit etc.
        if exchange_name == 'Binance':
            for ticker in raw_data:
                s = standardize_symbol_backend(ticker.get('symbol'), exchange_name)
                bid = decimal.Decimal(str(ticker.get('bidPrice', '0')))
                ask = decimal.Decimal(str(ticker.get('askPrice', '0')))
                if s and bid > 0 and ask > 0: all_tickers_map[s] = {'bidPrice': bid, 'askPrice': ask}
        elif exchange_name == 'Bybit':
            if raw_data.get('retCode') == 0 and raw_data.get('result') and isinstance(raw_data['result'].get('list'), list):
                for ticker in raw_data['result']['list']:
                    s = standardize_symbol_backend(ticker.get('symbol'), exchange_name)
                    bid = decimal.Decimal(str(ticker.get('bid1Price', '0')))
                    ask = decimal.Decimal(str(ticker.get('ask1Price', '0')))
                    if s and bid > 0 and ask > 0: all_tickers_map[s] = {'bidPrice': bid, 'askPrice': ask}
        elif exchange_name == 'OKX':
            if raw_data.get('code') == "0" and isinstance(raw_data.get('data'), list):
                for ticker in raw_data['data']:
                    s = standardize_symbol_backend(ticker.get('instId'), exchange_name)
                    bid = decimal.Decimal(str(ticker.get('bidPx', '0')))
                    ask = decimal.Decimal(str(ticker.get('askPx', '0')))
                    if s and bid > 0 and ask > 0: all_tickers_map[s] = {'bidPrice': bid, 'askPrice': ask}
        elif exchange_name == 'KuCoin':
            if raw_data.get('code') == "200000" and raw_data.get('data') and isinstance(raw_data['data'].get('ticker'), list):
                for ticker in raw_data['data']['ticker']:
                    s = standardize_symbol_backend(ticker.get('symbol'), exchange_name)
                    bid = decimal.Decimal(str(ticker.get('buy', '0')))
                    ask = decimal.Decimal(str(ticker.get('sell', '0')))
                    if s and bid > 0 and ask > 0: all_tickers_map[s] = {'bidPrice': bid, 'askPrice': ask}
        elif exchange_name == 'Gate':
            if isinstance(raw_data, list):
                 for ticker in raw_data:
                    s = standardize_symbol_backend(ticker.get('currency_pair'), exchange_name)
                    bid = decimal.Decimal(str(ticker.get('highest_bid', '0')))
                    ask = decimal.Decimal(str(ticker.get('lowest_ask', '0')))
                    if s and bid > 0 and ask > 0: all_tickers_map[s] = {'bidPrice': bid, 'askPrice': ask}
        elif exchange_name == 'MEXC':
            if isinstance(raw_data, list):
                 for ticker in raw_data:
                    s = standardize_symbol_backend(ticker.get('symbol'), exchange_name)
                    bid = decimal.Decimal(str(ticker.get('bidPrice', '0')))
                    ask = decimal.Decimal(str(ticker.get('askPrice', '0')))
                    if s and bid > 0 and ask > 0: all_tickers_map[s] = {'bidPrice': bid, 'askPrice': ask}
        elif exchange_name == 'HTX':
            if raw_data.get('status') == 'ok' and isinstance(raw_data.get('data'), list):
                for ticker in raw_data['data']:
                    s = standardize_symbol_backend(ticker.get('symbol'), exchange_name)
                    bid = decimal.Decimal(str(ticker.get('bid', '0')))
                    ask = decimal.Decimal(str(ticker.get('ask', '0')))
                    if s and bid > 0 and ask > 0: all_tickers_map[s] = {'bidPrice': bid, 'askPrice': ask}
        elif exchange_name == 'Bitget':
            if raw_data.get('code') == "00000" and isinstance(raw_data.get('data'), list):
                for ticker in raw_data['data']:
                    s = standardize_symbol_backend(ticker.get('symbolName') or ticker.get('symbol'), exchange_name)
                    bid = decimal.Decimal(str(ticker.get('buyOne', '0')))
                    ask = decimal.Decimal(str(ticker.get('sellOne', '0')))
                    if s and bid > 0 and ask > 0: all_tickers_map[s] = {'bidPrice': bid, 'askPrice': ask}
        elif exchange_name == 'Bitfinex':
            if isinstance(raw_data, list):
                for ticker_data in raw_data:
                    if isinstance(ticker_data, list) and len(ticker_data) >= 7 and isinstance(ticker_data[0], str) and ticker_data[0].startswith('t'):
                        s = standardize_symbol_backend(ticker_data[0], exchange_name)
                        bid = decimal.Decimal(str(ticker_data[1]))
                        ask = decimal.Decimal(str(ticker_data[3]))
                        if s and bid > 0 and ask > 0: all_tickers_map[s] = {'bidPrice': bid, 'askPrice': ask}
        elif exchange_name == 'BingX':
            if raw_data.get('code') == 0 and raw_data.get('data') and (isinstance(raw_data['data'].get('tickers'), list) or isinstance(raw_data['data'], list)):
                tickers_array = raw_data['data'].get('tickers') if isinstance(raw_data['data'].get('tickers'), list) else raw_data['data']
                for ticker in tickers_array:
                    s = standardize_symbol_backend(ticker.get('symbol'), exchange_name)
                    bid = decimal.Decimal(str(ticker.get('bidPrice', '0')))
                    ask = decimal.Decimal(str(ticker.get('askPrice', '0')))
                    if s and bid > 0 and ask > 0: all_tickers_map[s] = {'bidPrice': bid, 'askPrice': ask}
        else:
            print(f"Warning: No specific parsing logic implemented for {exchange_name} in fetch_exchange_ticker_data.")
    except requests.exceptions.RequestException as e:
        print(f"HTTP request failed for {exchange_name}: {e}")
        return {}
    except Exception as e:
        print(f"Error processing {exchange_name} data: {e}. Raw data preview: {str(raw_data)[:200]}")
        return {}
    return all_tickers_map


def fetch_specific_tickers_data(exchange_name, tracked_pairs_for_exchange, user_api_key_instance=None):
    """
    Fetches fresh bid/ask prices for a specific list of TrackedExchangePair instances.
    'tracked_pairs_for_exchange': A list/queryset of TrackedExchangePair objects for THIS exchange.
    Returns a ticker_map like {'STANDARDIZED_SYMBOL': {'bidPrice': X, 'askPrice': Y}}
    """
    config = EXCHANGE_API_CONFIG.get(exchange_name)
    if not config or not tracked_pairs_for_exchange: return {}

    raw_symbols_for_api_call = [pair.raw_exchange_symbol for pair in tracked_pairs_for_exchange]
    raw_to_std_map = {pair.raw_exchange_symbol: pair.symbol for pair in tracked_pairs_for_exchange}
    fetched_data_raw_key = {} # Stores { 'RAW_SYMBOL': {'bidPrice': X, 'askPrice': Y} }

    try:
        if exchange_name == 'Binance':
            # Binance /api/v3/ticker/bookTicker can take 'symbol' or 'symbols'
            # Using 'symbols' if multiple, 'symbol' if single.
            # public_ticker_url should be "https://api.binance.com/api/v3/ticker/bookTicker"
            base_url = config.get('public_ticker_url', "https://api.binance.com/api/v3/ticker/bookTicker")
            params = {}
            if len(raw_symbols_for_api_call) == 1:
                params = {'symbol': raw_symbols_for_api_call[0]}
            elif len(raw_symbols_for_api_call) > 1:
                # Max symbols might be an issue if list is very long (URL length limits).
                # Binance seems to prefer symbols as a JSON array string for the 'symbols' query param.
                params = {'symbols': json.dumps(raw_symbols_for_api_call)}
            else:
                return {}

            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            data_list = response.json()
            if not isinstance(data_list, list): data_list = [data_list]
            for item in data_list:
                fetched_data_raw_key[item['symbol']] = {
                    'bidPrice': decimal.Decimal(str(item['bidPrice'])),
                    'askPrice': decimal.Decimal(str(item['askPrice']))
                }

        elif exchange_name == 'Bybit':
            # Bybit /v5/market/tickers?category=spot does not take a list of symbols.
            # Fetch all and filter, or make individual calls. Re-using fetch_exchange_ticker_data.
            # fetch_exchange_ticker_data returns a map with STANDARD symbols as keys.
            all_bybit_tickers_std_keys = fetch_exchange_ticker_data(
                exchange_name,
                user_api_key_instance_map={exchange_name: user_api_key_instance} if user_api_key_instance else None
            )
            for pair_obj in tracked_pairs_for_exchange:
                if pair_obj.symbol in all_bybit_tickers_std_keys:
                    # Store with raw symbol as key temporarily, as per fetched_data_raw_key structure
                    fetched_data_raw_key[pair_obj.raw_exchange_symbol] = all_bybit_tickers_std_keys[pair_obj.symbol]

        # Add other exchanges:
        # For exchanges that support multi-symbol query (like Binance): Implement similar to Binance.
        # For exchanges that only support single-symbol query or all:
        #   - Option A: Loop and call single-symbol endpoint (can be slow if many symbols).
        #   - Option B (Simpler for now): Call existing fetch_exchange_ticker_data (gets all) and filter.
        #     This means fetch_exchange_ticker_data needs to be robust for those exchanges.
        elif config.get('url') or config.get('public_ticker_url'): # Fallback for other 'public' types
            print(f"Using fallback (all tickers then filter) for {exchange_name} specific fetch.")
            all_exchange_tickers_std_keys = fetch_exchange_ticker_data(
                exchange_name,
                user_api_key_instance_map={exchange_name: user_api_key_instance} if user_api_key_instance else None
            )
            for pair_obj in tracked_pairs_for_exchange:
                if pair_obj.symbol in all_exchange_tickers_std_keys:
                     fetched_data_raw_key[pair_obj.raw_exchange_symbol] = all_exchange_tickers_std_keys[pair_obj.symbol]
        else:
            print(f"No specific multi-symbol fetch logic for {exchange_name}, and no generic fallback URL defined in config.")


        # Standardize keys in the final map
        final_ticker_map = {}
        for raw_sym, data_val in fetched_data_raw_key.items():
            std_sym = raw_to_std_map.get(raw_sym)
            if std_sym:
                final_ticker_map[std_sym] = data_val

        # print(f"V2 Ticker Fetch for {exchange_name}: Requested {len(raw_symbols_for_api_call)}, Found in final map {len(final_ticker_map)}")
        return final_ticker_map

    except requests.exceptions.RequestException as e:
        print(f"Error in fetch_specific_tickers_data for {exchange_name}: {e}")
        return {}
    except Exception as e:
        print(f"Generic error in fetch_specific_tickers_data for {exchange_name}: {e}")
        return {}
