# arbitrage_platform/arbitrage_scanner/exchange_config.py
EXCHANGE_API_CONFIG = {
    'Binance': {
        'type': 'client_or_public', # Indicates we can use our client or a public URL
        'public_ticker_url': "https://api.binance.com/api/v3/ticker/bookTicker",
        'client_method_tickers': 'get_book_tickers', # Method in BinanceClient
        'client_class_ref': 'exchange_clients.binance_client.BinanceClient' # Path to client
    },
    'Bybit': {
        'type': 'client_or_public',
        'public_ticker_url': "https://api.bybit.com/v5/market/tickers?category=spot",
        'client_method_tickers': 'get_spot_tickers', # Method in BybitClient
        'client_class_ref': 'exchange_clients.bybit_client.BybitClient'
    },
    'OKX': {'type': 'public', 'url': "https://www.okx.com/api/v5/market/tickers?instType=SPOT"},
    'KuCoin': {'type': 'public', 'url': "https://api.kucoin.com/api/v1/market/allTickers"},
    # Add other exchanges from the original JS API_CONFIG that have public ticker URLs
    # For exchanges with multi-step public APIs (like Coinbase, Kraken from original JS),
    # that logic would need to be ported here too, or simplified if possible.
    # For now, focus on direct public URLs for simplicity for non-Binance/Bybit.
    'Gate': {'type': 'public', 'url': "https://api.gateio.ws/api/v4/spot/tickers"},
    'MEXC': {'type': 'public', 'url': "https://api.mexc.com/api/v3/ticker/bookTicker"},
    'HTX': {'type': 'public', 'url': "https://api.htx.com/market/tickers"},
    'Bitget': {'type': 'public', 'url': "https://api.bitget.com/api/v2/spot/market/tickers"},
    'Bitfinex': {'type': 'public', 'url': "https://api-pub.bitfinex.com/v2/tickers?symbols=ALL"},
    'BingX': {'type': 'public', 'url': "https://open-api.bingx.com/openApi/spot/v1/market/ticker"},
    # Coinbase, Upbit, CryptoCom, Kraken would require more complex 'type' handlers
    # for their multi-step public API processes if not using a dedicated client for them.
}

# Helper to dynamically import client classes
import importlib
def get_client_class(class_path_string):
    module_name, class_name = class_path_string.rsplit('.', 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)
