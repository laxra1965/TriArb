from .base_client import BaseExchangeClient, APIKeyRequiredError, ExchangeAPIError
import time
import hmac
import hashlib
import json
import decimal
import uuid # For clientOrderId

class BybitClient(BaseExchangeClient):
    BASE_API_URL = "https://api.bybit.com"
    # TESTNET_BASE_API_URL = "https://api-testnet.bybit.com"

    def __init__(self, user_api_key_instance=None, is_testnet=False):
        super().__init__(user_api_key_instance)
        # if is_testnet:
        #     self.BASE_API_URL = self.TESTNET_BASE_API_URL

    def _generate_bybit_v5_signature(self, timestamp, api_key, recv_window, payload_string=""):
        # (As implemented in previous step, ensuring payload_string is correct for GET/POST)
        if not self.api_secret:
            raise APIKeyRequiredError("API secret is required to generate signature.")
        # Ensure all parts of the string are strings themselves before concatenation
        string_to_sign = str(timestamp) + str(api_key) + str(recv_window) + str(payload_string)
        return hmac.new(self.api_secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    def get_account_balance(self, account_type="UNIFIED"):
        # (As implemented in previous step)
        if not self.api_key or not self.api_secret:
            raise APIKeyRequiredError("API key and secret required for account balance.")
        endpoint = "/v5/account/wallet-balance"
        timestamp = str(int(time.time() * 1000))
        recv_window = "20000" # Bybit's recommendation for recv_window is string
        params = {'accountType': account_type}
        # Parameters must be sorted alphabetically for Bybit signature generation for GET requests
        sorted_params_query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])

        signature = self._generate_bybit_v5_signature(timestamp, self.api_key, recv_window, sorted_params_query)

        headers = {
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-SIGN': signature,
            'X-BAPI-SIGN-TYPE': '2', # HMAC_SHA256
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-RECV-WINDOW': recv_window,
            'Content-Type': 'application/json'
        }
        response_data = self._get_request(endpoint, params=params, headers=headers, signed=True) # signed=True for key check
        balances = {}
        if response_data and response_data.get('retCode') == 0 and 'result' in response_data and 'list' in response_data['result']:
            for account_info in response_data['result']['list']:
                 # Ensure it's the primary list item, not nested structures if any
                if isinstance(account_info, dict) and (account_info.get('accountType') == account_type or \
                   (account_type == "UNIFIED" and account_info.get('accountType') in ["UNIFIED", "CONTRACT", "SPOT"])):
                    for coin_info in account_info.get('coin', []):
                        asset = coin_info.get('coin')
                        equity = decimal.Decimal(coin_info.get('equity', '0'))
                        available_balance = decimal.Decimal(coin_info.get('availableToWithdraw', coin_info.get('availableBalance', '0')))
                        wallet_balance = decimal.Decimal(coin_info.get('walletBalance', '0'))
                        locked_balance = wallet_balance - available_balance

                        if asset:
                            balances[asset] = {
                                'free': available_balance,
                                'locked': locked_balance if locked_balance >= decimal.Decimal('0') else decimal.Decimal('0'),
                                'total': wallet_balance
                            }
        return balances

    def create_market_order(self, pair_symbol, side, quantity, category="spot"):
        """
        Places a market order using Bybit V5 API.
        :param pair_symbol: e.g., "BTCUSDT"
        :param side: "Buy" or "Sell" (case-sensitive for Bybit)
        :param quantity: Amount of base asset (for spot). For SELL, it's base qty. For BUY, it's base qty.
        :param category: "spot" or "linear" or "inverse"
        """
        if not self.api_key or not self.api_secret:
            raise APIKeyRequiredError("API key and secret required for placing orders.")

        endpoint = "/v5/order/create"
        timestamp = str(int(time.time() * 1000))
        recv_window = "20000"

        client_order_id = f"custom_{uuid.uuid4().hex[:16]}"

        order_payload = {
            "category": category,
            "symbol": pair_symbol.upper(),
            "side": side,
            "orderType": "Market",
            "qty": f"{decimal.Decimal(quantity):.8f}", # Format quantity as string with precision
            "orderLinkId": client_order_id,
        }

        payload_json_string = json.dumps(order_payload)
        signature = self._generate_bybit_v5_signature(timestamp, self.api_key, recv_window, payload_json_string)

        headers = {
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-SIGN': signature,
            'X-BAPI-SIGN-TYPE': '2',
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-RECV-WINDOW': recv_window,
            'Content-Type': 'application/json'
        }

        response_data = self._post_request(endpoint, data=payload_json_string, headers=headers, signed=True)
        return response_data

    def get_order_status(self, pair_symbol, order_id=None, client_order_id=None, category="spot"):
        """
        Checks order status using Bybit V5 API.
        Either order_id or client_order_id (orderLinkId) must be provided.
        """
        if not self.api_key or not self.api_secret:
            raise APIKeyRequiredError("API key and secret required for checking order status.")
        if not order_id and not client_order_id:
            raise ValueError("Either order_id or client_order_id (orderLinkId) must be provided.")

        endpoint = "/v5/order/history"
        timestamp = str(int(time.time() * 1000))
        recv_window = "20000"

        params = {"category": category, "symbol": pair_symbol.upper()}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["orderLinkId"] = client_order_id

        sorted_params_query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = self._generate_bybit_v5_signature(timestamp, self.api_key, recv_window, sorted_params_query)

        headers = {
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-SIGN': signature,
            'X-BAPI-SIGN-TYPE': '2',
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-RECV-WINDOW': recv_window,
            'Content-Type': 'application/json'
        }

        response_data = self._get_request(endpoint, params=params, headers=headers, signed=True)

        if response_data and response_data.get('retCode') == 0 and 'result' in response_data and isinstance(response_data['result'].get('list'), list):
            if len(response_data['result']['list']) > 0:
                return response_data['result']['list'][0]
            return {"message": "Order not found in history."}
        return response_data

    def get_spot_tickers(self): # From previous step
        endpoint = "/v5/market/tickers"
        params = {'category': 'spot'}
        return self._get_request(endpoint, params=params, signed=False)

    def get_order_book_depth(self, pair_symbol, limit=5, category="spot"): # Bybit default limit is 1, max 50 for spot L1
        """
        Fetches order book depth for a symbol using Bybit V5 API.
        :param pair_symbol: e.g., "BTCUSDT"
        :param limit: Number of bids/asks. Bybit V5 /v5/market/orderbook. Default limit for spot is 1, max 50.
                        For deeper depth, consider L2 or L3 data if available and needed.
        :param category: "spot", "linear", "inverse"
        """
        endpoint = "/v5/market/orderbook"
        # Bybit limit for spot is 1, or a value up to 50.
        # Common values might be 1, 25, 50. Let's ensure it's within a valid range for Bybit.
        if category == "spot":
            if limit <= 1: limit = 1
            elif limit > 50: limit = 50
            # Bybit specific valid limits for spot: 1, 50. Some docs mention up to 200 for spot.
            # For safety and common use, sticking to 50 as max if not 1.
            # If the user requests between 2-49, it might be best to pick 1 or 50.
            # Or pass it as is if the API handles it gracefully. For now, cap at 50.

        params = {'category': category, 'symbol': pair_symbol.upper()}
        if limit > 0 : # limit 0 or negative is not valid for Bybit.
             params['limit'] = limit

        # Public endpoint
        response_data = self._get_request(endpoint, params=params, signed=False)
        # Response structure: result: { "s": "BTCUSDT", "a": [["price", "qty"]...], "b": [["price", "qty"]...], "ts": ..., "u": ...}

        # Convert price/qty strings to Decimals and standardize key names 'bids', 'asks'
        if response_data and response_data.get('retCode') == 0 and 'result' in response_data:
            result = response_data['result']
            parsed_result = {'s': result.get('s'), 'ts': result.get('ts'), 'lastUpdateId': result.get('u')} # Bybit uses 'u' for updateId

            if 'b' in result and isinstance(result['b'], list): # bids
                parsed_result['bids'] = [[decimal.Decimal(b_item[0]), decimal.Decimal(b_item[1])] for b_item in result['b'] if isinstance(b_item, list) and len(b_item) == 2]
            else:
                parsed_result['bids'] = []

            if 'a' in result and isinstance(result['a'], list): # asks
                parsed_result['asks'] = [[decimal.Decimal(a_item[0]), decimal.Decimal(a_item[1])] for a_item in result['a'] if isinstance(a_item, list) and len(a_item) == 2]
            else:
                parsed_result['asks'] = []
            return parsed_result
        return response_data # Return full response if error or unexpected structure
