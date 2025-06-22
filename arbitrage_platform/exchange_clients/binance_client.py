from .base_client import BaseExchangeClient, APIKeyRequiredError, ExchangeAPIError
import time
import hmac
import hashlib
from urllib.parse import urlencode
import decimal

class BinanceClient(BaseExchangeClient):
    BASE_API_URL = "https://api.binance.com"
    # TESTNET_BASE_API_URL = "https://testnet.binance.vision"

    def __init__(self, user_api_key_instance=None, is_testnet=False):
        super().__init__(user_api_key_instance)
        # if is_testnet:
        #     self.BASE_API_URL = self.TESTNET_BASE_API_URL
        # For this subtask, actual calls won't be made.
        # Ensure self.api_key and self.api_secret are available from super()

    def _generate_binance_signature(self, data_string):
        # (As implemented in previous step)
        if not self.api_secret:
            raise APIKeyRequiredError("API secret is required to generate signature.")
        return hmac.new(self.api_secret.encode('utf-8'), data_string.encode('utf-8'), hashlib.sha256).hexdigest()

    def get_server_time(self):
        # (As implemented in previous step)
        endpoint = "/api/v3/time"
        return self._get_request(endpoint, signed=False)

    def get_account_balance(self):
        # (As implemented in previous step)
        if not self.api_key or not self.api_secret:
            raise APIKeyRequiredError("API key and secret required for account balance.")
        endpoint = "/api/v3/account"
        timestamp = int(time.time() * 1000)
        params = {'timestamp': timestamp, 'recvWindow': 5000}
        query_string = urlencode(params)
        signature = self._generate_binance_signature(query_string)
        params['signature'] = signature
        headers = {'X-MBX-APIKEY': self.api_key}
        response_data = self._get_request(endpoint, params=params, headers=headers, signed=True)
        balances = {}
        if response_data and 'balances' in response_data:
            for asset_info in response_data['balances']:
                asset = asset_info.get('asset')
                free = asset_info.get('free')
                locked = asset_info.get('locked')
                if asset and free is not None and locked is not None:
                    balances[asset] = {
                        'free': decimal.Decimal(free),
                        'locked': decimal.Decimal(locked),
                        'total': decimal.Decimal(free) + decimal.Decimal(locked)
                    }
        return balances

    def create_market_order(self, pair_symbol, side, quantity):
        """
        Places a market order.
        :param pair_symbol: e.g., "BTCUSDT"
        :param side: "BUY" or "SELL"
        :param quantity: Amount of base asset to buy/sell (e.g., for BTCUSDT, quantity is in BTC)
                         For SELL, this is the quantity of the base asset you are selling.
                         For BUY, if quoteOrderQty is not used, this is the quantity of the base asset you want to buy.
                         Alternatively, for BUY market orders, 'quoteOrderQty' (total USDT to spend) can be used.
                         This example uses 'quantity'.
        """
        if not self.api_key or not self.api_secret:
            raise APIKeyRequiredError("API key and secret required for placing orders.")

        endpoint = "/api/v3/order"
        timestamp = int(time.time() * 1000)
        params = {
            'symbol': pair_symbol.upper(),
            'side': side.upper(),
            'type': 'MARKET',
            # Format quantity to required precision by Binance, ensure it's a string
            'quantity': f"{decimal.Decimal(quantity):.8f}",
            'timestamp': timestamp,
            'recvWindow': 5000
        }
        # For quoteOrderQty on BUY market orders:
        # if side.upper() == 'BUY':
        #     params.pop('quantity', None) # Remove quantity if using quoteOrderQty
        #     params['quoteOrderQty'] = f"{quantity_in_quote_asset:.8f}"


        payload_string = urlencode(params)
        signature = self._generate_binance_signature(payload_string)
        params['signature'] = signature

        headers = {'X-MBX-APIKEY': self.api_key}

        # Market orders are POST requests
        response_data = self._post_request(endpoint, data=params, headers=headers, signed=True)
        return response_data # Contains orderId, status, fills, etc.

    def get_order_status(self, pair_symbol, order_id=None, orig_client_order_id=None):
        """
        Checks the status of an order.
        Either order_id or orig_client_order_id must be provided.
        """
        if not self.api_key or not self.api_secret:
            raise APIKeyRequiredError("API key and secret required for checking order status.")
        if not order_id and not orig_client_order_id:
            raise ValueError("Either order_id or orig_client_order_id must be provided.")

        endpoint = "/api/v3/order"
        timestamp = int(time.time() * 1000)
        params = {
            'symbol': pair_symbol.upper(),
            'timestamp': timestamp,
            'recvWindow': 5000
        }
        if order_id:
            params['orderId'] = order_id
        if orig_client_order_id:
            params['origClientOrderId'] = orig_client_order_id

        query_string = urlencode(params)
        signature = self._generate_binance_signature(query_string)
        params['signature'] = signature

        headers = {'X-MBX-APIKEY': self.api_key}
        response_data = self._get_request(endpoint, params=params, headers=headers, signed=True)
        return response_data # Contains status, executedQty, price, etc.

    def get_book_tickers(self): # From previous step
        endpoint = "/api/v3/ticker/bookTicker"
        return self._get_request(endpoint, signed=False)

    def get_order_book_depth(self, pair_symbol, limit=5):
        """
        Fetches order book depth (top bids/asks) for a symbol.
        :param pair_symbol: e.g., "BTCUSDT"
        :param limit: Number of bids/asks to retrieve (e.g., 5, 10, 20, 50, 100, 500, 1000). Default 5.
                        Check Binance API docs for valid limits. Max is often 1000.
        """
        endpoint = "/api/v3/depth"
        params = {'symbol': pair_symbol.upper(), 'limit': limit}
        # This is a public endpoint, no signing needed usually for depth unless specific permissions
        response_data = self._get_request(endpoint, params=params, signed=False)
        # Response structure: {"lastUpdateId": ..., "bids": [["price", "qty"], ...], "asks": [["price", "qty"], ...]}

        # Convert price/qty strings to Decimals
        if response_data:
            if 'bids' in response_data and isinstance(response_data['bids'], list):
                response_data['bids'] = [[decimal.Decimal(b[0]), decimal.Decimal(b[1])] for b in response_data['bids'] if isinstance(b, list) and len(b) == 2]
            if 'asks' in response_data and isinstance(response_data['asks'], list):
                response_data['asks'] = [[decimal.Decimal(a[0]), decimal.Decimal(a[1])] for a in response_data['asks'] if isinstance(a, list) and len(a) == 2]
        return response_data
