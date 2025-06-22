import requests
import time
import hmac
import hashlib
from urllib.parse import urlencode

class BaseExchangeClientException(Exception):
    """Base exception for exchange client errors."""
    pass

class APIKeyRequiredError(BaseExchangeClientException):
    """Raised when an API key is required but not provided."""
    pass

class ExchangeAPIError(BaseExchangeClientException):
    """Raised when the exchange API returns an error."""
    def __init__(self, status_code, error_data):
        self.status_code = status_code
        self.error_data = error_data
        message = f"API Error {status_code}: {error_data}"
        super().__init__(message)


class BaseExchangeClient:
    BASE_API_URL = '' # To be overridden by subclasses

    def __init__(self, user_api_key_instance=None):
        """
        Initializes the client.
        :param user_api_key_instance: Optional UserAPIKey model instance.
                                      If provided, api_key and api_secret will be used.
        """
        self.api_key = None
        self.api_secret = None
        if user_api_key_instance:
            self.api_key = user_api_key_instance.api_key
            self.api_secret = user_api_key_instance.get_api_secret() # Decrypts here

    def _get_request(self, endpoint, params=None, headers=None, signed=False):
        return self._request('GET', endpoint, params=params, headers=headers, signed=signed)

    def _post_request(self, endpoint, data=None, headers=None, signed=True):
        return self._request('POST', endpoint, data=data, headers=headers, signed=signed)

    def _request(self, method, endpoint, params=None, data=None, headers=None, signed=False):
        if signed and (not self.api_key or not self.api_secret):
            raise APIKeyRequiredError("Authenticated endpoint requires API key and secret.")

        url = f"{self.BASE_API_URL}{endpoint}"

        # Default headers if none provided
        request_headers = headers if headers is not None else {}

        # Placeholder for actual request logic, signing, etc.
        # This will be implemented more specifically in subclasses
        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=request_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, params=params, data=data, headers=request_headers, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Attempt to get more specific error data from response if possible
            error_data = None
            try:
                error_data = e.response.json()
            except ValueError: # response not JSON
                error_data = e.response.text
            raise ExchangeAPIError(status_code=e.response.status_code, error_data=error_data) from e
        except requests.exceptions.RequestException as e: # Other errors like connection error
            raise BaseExchangeClientException(f"Request failed: {e}") from e

    # Helper for generating signatures (example, will vary by exchange)
    def _generate_signature(self, data_string):
        # This is a generic placeholder. Each exchange has its own method.
        # For HMAC-SHA256:
        # return hmac.new(self.api_secret.encode('utf-8'), data_string.encode('utf-8'), hashlib.sha256).hexdigest()
        raise NotImplementedError("Signature generation must be implemented by subclass.")

    def get_server_time(self):
        # Example: many exchanges have a server time endpoint
        raise NotImplementedError("get_server_time must be implemented by subclass.")
