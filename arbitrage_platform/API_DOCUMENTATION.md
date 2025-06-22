# Arbitrage Platform API Documentation

This document provides details on the available API endpoints for the Arbitrage Platform.

**Base URL:** `/api/` (All endpoints listed below are prefixed with this)

## Authentication (`/api/auth/`)

All authentication-related endpoints.

### 1. User Registration
-   **Endpoint:** `POST /api/auth/register/`
-   **Description:** Registers a new user.
-   **Authentication:** None required.
-   **Request Body (JSON):**
    ```json
    {
        "username": "newuser",
        "email": "user@example.com",
        "password": "YourStrongPassword123",
        "password2": "YourStrongPassword123",
        "first_name": "Test",
        "last_name": "User"
    }
    ```
-   **Success Response (201 Created):**
    ```json
    {
        "username": "newuser",
        "email": "user@example.com",
        "first_name": "Test",
        "last_name": "User"
        // Other fields from UserRegistrationSerializer might be present
    }
    ```
-   **Error Responses:**
    -   `400 Bad Request`: If validation fails (e.g., passwords don't match, username/email already exists, missing fields). Example:
        ```json
        {
            "username": ["A user with that username already exists."]
        }
        ```

### 2. User Login (Token Obtain)
-   **Endpoint:** `POST /api/auth/token/`
-   **Description:** Logs in an existing user and returns JWT access and refresh tokens.
-   **Authentication:** None required.
-   **Request Body (JSON):**
    ```json
    {
        "username": "existinguser",
        "password": "TheirPassword123"
    }
    ```
-   **Success Response (200 OK):**
    ```json
    {
        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```
-   **Error Responses:**
    -   `401 Unauthorized`: If credentials are invalid.
        ```json
        {
            "detail": "No active account found with the given credentials"
        }
        ```
    -   `429 Too Many Requests`: If login attempts are rate-limited.

### 3. Token Refresh
-   **Endpoint:** `POST /api/auth/token/refresh/`
-   **Description:** Obtains a new JWT access token using a valid refresh token.
-   **Authentication:** None required (but valid refresh token is needed).
-   **Request Body (JSON):**
    ```json
    {
        "refresh": "your_valid_refresh_token_here"
    }
    ```
-   **Success Response (200 OK):**
    ```json
    {
        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." // New refresh token if ROTATE_REFRESH_TOKENS is True
    }
    ```
-   **Error Responses:**
    -   `401 Unauthorized`: If refresh token is invalid, expired, or blacklisted.
        ```json
        {
            "detail": "Token is invalid or expired",
            "code": "token_not_valid"
        }
        ```

### 4. Token Blacklist (Logout)
-   **Endpoint:** `POST /api/auth/token/blacklist/`
-   **Description:** Blacklists a refresh token, effectively logging the user out from that refresh token's session chain. Client should discard both access and refresh tokens.
-   **Authentication:** None required by default for this endpoint (it accepts a refresh token).
-   **Request Body (JSON):**
    ```json
    {
        "refresh": "your_valid_refresh_token_to_blacklist"
    }
    ```
-   **Success Response (200 OK):**
    ```json
    {}
    ```
    (Or specific success message based on SimpleJWT configuration)
-   **Error Responses:**
    -   `400 Bad Request`: If refresh token is malformed.
    -   `401 Unauthorized`: If refresh token is already blacklisted or invalid.

## User Profile & API Key Management (`/api/auth/`)

### 1. User Profile
-   **Endpoint:** `GET /api/auth/users/me/`
-   **Description:** Retrieves the profile of the currently authenticated user, including nested wallet information.
-   **Authentication:** JWT Required.
-   **Success Response (200 OK):**
    ```json
    {
        "id": 1,
        "username": "currentuser",
        "email": "currentuser@example.com",
        "first_name": "Current",
        "last_name": "User",
        "wallet": {
            "balance": "123.45000000", // Serialized Decimal
            "updated_at": "2023-10-27T10:30:00Z"
        },
        "date_joined": "2023-10-26T10:00:00Z",
        "last_login": "2023-10-27T10:00:00Z"
    }
    ```
-   **Error Responses:**
    -   `401 Unauthorized`: If not authenticated.

### 2. Exchange Choices for API Keys
-   **Endpoint:** `GET /api/auth/exchange-choices/`
-   **Description:** Retrieves a list of available exchange choices for configuring API keys.
-   **Authentication:** JWT Required.
-   **Success Response (200 OK):**
    ```json
    [
        {"value": "Binance", "label": "Binance"},
        {"value": "Bybit", "label": "Bybit"}
        // ... other configured exchanges
    ]
    ```
-   **Error Responses:**
    -   `401 Unauthorized`: If not authenticated.

### 3. API Key Management (`/api/auth/keys/`)
-   **List API Keys:**
    -   **Endpoint:** `GET /api/auth/keys/`
    -   **Description:** Lists all API keys for the authenticated user.
    -   **Authentication:** JWT Required.
    -   **Success Response (200 OK):** (Paginated)
        ```json
        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "id": 1,
                    "user": 1, // User ID
                    "exchange_name": "Binance",
                    "api_key": "your_api_key_here_public_part",
                    // "_api_secret_encrypted": "ENCRYPTED_VALUE_IF_EXPOSED", // Typically not exposed in list
                    "created_at": "2023-10-27T11:00:00Z",
                    "updated_at": "2023-10-27T11:00:00Z"
                }
            ]
        }
        ```
-   **Create API Key:**
    -   **Endpoint:** `POST /api/auth/keys/`
    -   **Description:** Adds a new API key for the authenticated user.
    -   **Authentication:** JWT Required.
    -   **Request Body (JSON):**
        ```json
        {
            "exchange_name": "Binance",
            "api_key": "your_new_api_key",
            "api_secret": "your_new_api_secret"
        }
        ```
    -   **Success Response (201 Created):** (Similar to one item in the list response, `api_secret` not returned)
-   **Retrieve API Key:**
    -   **Endpoint:** `GET /api/auth/keys/{id}/`
    -   **Description:** Retrieves details of a specific API key owned by the user.
    -   **Authentication:** JWT Required.
    -   **Success Response (200 OK):** (Similar to one item in list, `api_secret` not returned)
-   **Update API Key:**
    -   **Endpoint:** `PUT /api/auth/keys/{id}/`
    -   **Description:** Updates an existing API key (e.g., key, secret, or other editable fields if any).
    -   **Authentication:** JWT Required.
    -   **Request Body (JSON):** (Fields to update)
        ```json
        {
            "api_key": "updated_api_key",
            "api_secret": "updated_api_secret"
            // "exchange_name": "Binance" // Usually not changed
        }
        ```
    -   **Success Response (200 OK):** (Updated object, `api_secret` not returned)
-   **Delete API Key:**
    -   **Endpoint:** `DELETE /api/auth/keys/{id}/`
    -   **Description:** Deletes an API key.
    -   **Authentication:** JWT Required.
    -   **Success Response (204 No Content):**
-   **Error Responses (for API Key Management):**
    -   `400 Bad Request`: Validation errors (e.g., missing fields, duplicate user/exchange).
    -   `401 Unauthorized`: Not authenticated.
    -   `403 Forbidden`: (Less likely with default IsAuthenticated, but if object-level permissions were stricter and failed).
    -   `404 Not Found`: If trying to access/modify a key that doesn't exist or doesn't belong to the user.

## Wallet Management (`/api/wallet/`)

### 1. Deposit Requests
-   **Create Deposit Request:**
    -   **Endpoint:** `POST /api/wallet/deposit-requests/`
    -   **Description:** User initiates a request to deposit funds (e.g., USDT).
    -   **Authentication:** JWT Required.
    -   **Request Body (JSON):**
        ```json
        {
            "amount_requested": "100.00", // Decimal as string
            "blockchain_tx_id": "optional_user_provided_tx_id_if_already_sent"
        }
        ```
    -   **Success Response (201 Created):**
        ```json
        {
            "message": "Deposit request created. Please send funds to the address below if you haven't already.",
            "deposit_address_USDT_TRC20": "YOUR_STATIC_USDT_TRC20_WALLET_ADDRESS_PLACEHOLDER",
            "qr_code_url_USDT_TRC20": "/static/images/placeholder_qr_code.png",
            "request_details": {
                "id": "uuid-of-request",
                "user": 1,
                "amount_requested": "100.00000000",
                "currency": "USDT",
                "status": "pending_user_action", // or 'pending_confirmation' if tx_id provided
                "status_display": "Pending User Action",
                "created_at": "2023-10-27T12:00:00Z",
                "blockchain_tx_id": "optional_user_provided_tx_id_if_already_sent"
            }
        }
        ```
    -   **Error Responses:**
        -   `400 Bad Request`: Invalid amount (e.g., below minimum).
        -   `401 Unauthorized`.
-   **List Deposit Requests:**
    -   **Endpoint:** `GET /api/wallet/deposit-requests/`
    -   **Description:** Lists deposit requests for the authenticated user.
    -   **Authentication:** JWT Required.
    -   **Success Response (200 OK):** (Paginated list of deposit request objects similar to `request_details` above).

### 2. Wallet Transactions
-   **Endpoint:** `GET /api/wallet/transactions/`
-   **Description:** Lists all wallet transactions (credits, debits) for the authenticated user.
-   **Authentication:** JWT Required.
-   **Success Response (200 OK):** (Paginated list)
    ```json
    {
        "count": 1,
        "next": null,
        "previous": null,
        "results": [
            {
                "id": 1,
                "wallet": 1, // Wallet ID
                "transaction_type": "credit",
                "transaction_type_display": "Credit",
                "amount": "100.00000000",
                "timestamp": "2023-10-27T12:05:00Z",
                "description": "Deposit confirmed for request ..."
            }
        ]
    }
    ```
-   **Error Responses:**
    -   `401 Unauthorized`.

## Arbitrage Scanner (`/api/scanner/`)

### 1. Fetch Arbitrage Opportunities
-   **Endpoint:** `GET /api/scanner/opportunities/`
-   **Description:** Fetches potential triangular arbitrage opportunities.
-   **Authentication:** JWT Required.
-   **Query Parameters (Optional):**
    -   `version`: `v1` or `v2` (defaults to `v1`). Selects the scanner logic.
    -   `exchanges`: Comma-separated list of exchange names (e.g., `Binance,Bybit`). Defaults to all configured.
    -   `base_coin`: The base currency for calculations (e.g., `USDT`, `BTC`). Defaults to `USDT`.
    -   `start_amount`: The initial amount for simulation (e.g., `10.0`). Defaults to `10.0`.
-   **Success Response (200 OK):**
    ```json
    [
        {
            "exchange": "Binance",
            "path": ["BTCUSDT", "ETHBTC", "ETHUSDT"],
            "coins": ["USDT", "BTC", "ETH"],
            "start_amount": 10.0,
            "final_amount": 10.05, // Example
            "profit": 0.05,
            "profit_percent": 0.5,
            "steps_description": [
                "BUY BTC with USDT using BTCUSDT @ 30000.00000000",
                "BUY ETH with BTC using ETHBTC @ 0.07000000",
                "SELL ETH for USDT using ETHUSDT @ 2105.00000000"
            ],
            "rates": [30000.0, 0.07, 2105.0],
            "intermediate_amounts": [10.0, 0.00033333, 0.00476185, 10.02379425],
            "actions_for_service": ["BUY", "BUY", "SELL"],
            "base_coin_for_service": "USDT",
            "asset_sequence": ["USDT", "BTC", "ETH", "USDT"],
            "scanner_version": "v1" // or "v2"
        }
        // ... more opportunities
    ]
    ```
-   **Error Responses:**
    -   `401 Unauthorized`.
    -   `402 Payment Required`: If user's wallet balance is below `MINIMUM_SCANNER_ACCESS_BALANCE`.
    -   `400 Bad Request`: Invalid `version` parameter or other input issues.
    -   `500 Internal Server Error`: If an error occurs during the scan.

## Trading Engine (`/api/trading/`)

### 1. Execute Arbitrage Trade
-   **Endpoint:** `POST /api/trading/execute/`
-   **Description:** Attempts to execute a given arbitrage opportunity.
-   **Authentication:** JWT Required.
-   **Request Body (JSON):**
    ```json
    {
        "opportunity": { /* The full opportunity object from the scanner endpoint */
            "exchange": "Binance",
            "path": ["BTCUSDT", "ETHBTC", "ETHUSDT"],
            "coins": ["USDT", "BTC", "ETH"],
            "asset_sequence": ["USDT", "BTC", "ETH", "USDT"],
            "rates": [30000.0, 0.07, 2100.0],
            "profit_percent": 0.1,
            "profit": "0.1",
            "actions_for_service": ["BUY", "BUY", "SELL"],
            "base_coin_for_service": "USDT"
            // ... other fields from the opportunity
        },
        "start_amount": "10.0" // The amount of base_coin_for_service to start with
    }
    ```
-   **Success Response (200 OK):**
    ```json
    {
        "message": "Trade execution process finished.",
        "trade_attempt_id": "uuid-of-trade-attempt",
        "status": "completed", // or "failed", "in_progress"
        "final_amount_base_coin": "10.08", // Example, after profit and commission
        "actual_profit": "0.08", // Example
        "legs": [
            { "leg_number": 1, "pair": "BTCUSDT", "side": "BUY", "status": "filled", "exchange_order_id": "123", "error_message": null },
            { "leg_number": 2, "pair": "ETHBTC", "side": "BUY", "status": "filled", "exchange_order_id": "124", "error_message": null },
            { "leg_number": 3, "pair": "ETHUSDT", "side": "SELL", "status": "filled", "exchange_order_id": "125", "error_message": null }
        ]
    }
    ```
-   **Error Responses:**
    -   `400 Bad Request`: Missing data, validation error from `TradeExecutionService` (e.g., depth check fail, API key not found).
    -   `401 Unauthorized`.
    -   `500 Internal Server Error`: Critical error during execution.
    -   `502 Bad Gateway`: If an exchange API error occurs during trade.

### 2. List Trade Attempts
-   **Endpoint:** `GET /api/trading/trade-attempts/`
-   **Description:** Lists all arbitrage trade attempts for the authenticated user.
-   **Authentication:** JWT Required.
-   **Success Response (200 OK):** (Paginated list of `ArbitrageTradeAttempt` objects, including nested legs, similar to `ArbitrageTradeAttemptSerializer` output).

### 3. List Trade Legs
-   **Endpoint:** `GET /api/trading/trade-legs/`
-   **Description:** Lists trade legs. Can be filtered by `attempt_id`.
-   **Authentication:** JWT Required.
-   **Query Parameters (Optional):**
    -   `attempt_id`: UUID of the `ArbitrageTradeAttempt` to filter legs for.
-   **Success Response (200 OK):** (Paginated list of `TradeOrderLeg` objects, similar to `TradeOrderLegSerializer` output).

## Notifications (`/api/notifications/`)

### 1. List User Notifications
-   **Endpoint:** `GET /api/notifications/user-notifications/`
-   **Description:** Lists notifications for the authenticated user.
-   **Authentication:** JWT Required.
-   **Query Parameters (Optional):**
    -   `is_read`: `true` or `false` to filter by read status.
-   **Success Response (200 OK):** (Paginated list)
    ```json
    {
        "count": 1,
        "next": null,
        "previous": null,
        "results": [
            {
                "id": "uuid-of-notification",
                "message": "Your trade attempt XYZ has completed.",
                "notification_type": "trade",
                "notification_type_display": "Trade Update",
                "is_read": false,
                "created_at": "2023-10-27T13:00:00Z",
                "updated_at": "2023-10-27T13:00:00Z"
            }
        ]
    }
    ```
-   **Error Responses:**
    -   `401 Unauthorized`.

### 2. Mark Notification as Read
-   **Endpoint:** `POST /api/notifications/user-notifications/{id}/mark_as_read/`
-   **Description:** Marks a specific notification as read.
-   **Authentication:** JWT Required.
-   **Request Body:** Empty.
-   **Success Response (200 OK):**
    ```json
    {
        "status": "notification marked as read"
    }
    ```
-   **Error Responses:**
    -   `401 Unauthorized`.
    -   `404 Not Found`: If notification ID does not exist or does not belong to the user.

### 3. Mark All Notifications as Read
-   **Endpoint:** `POST /api/notifications/user-notifications/mark_all_as_read/`
-   **Description:** Marks all unread notifications for the user as read.
-   **Authentication:** JWT Required.
-   **Request Body:** Empty.
-   **Success Response (200 OK):**
    ```json
    {
        "status": "X notifications marked as read"
    }
    ```
-   **Error Responses:**
    -   `401 Unauthorized`.

## WebSocket Endpoints (Conceptual)

Real-time updates are provided over WebSockets. Clients should establish a WebSocket connection to the relevant endpoint after authenticating (e.g., by obtaining a JWT).

-   **Notification Updates:** `ws/user_notifications/`
    -   Receives new notifications for the user.
-   **Wallet Updates:** `ws/wallet_updates/`
    -   Receives updates when the user's wallet balance changes.
-   **Trade Status Updates:** `ws/trade_status_updates/`
    -   Receives updates on the status of `ArbitrageTradeAttempt` and `TradeOrderLeg` instances.

**Authentication for WebSockets:**
-   The current setup uses Django's session-based authentication via `AuthMiddlewareStack`. This means if a user is logged into the Django admin panel or has an active session cookie from the web interface, they will be authenticated on the WebSocket.
-   For pure API-driven clients (e.g., a SPA using only JWTs), the JWT could be passed as a query parameter in the WebSocket connection URL (e.g., `ws/user_notifications/?token=YOUR_JWT`). Custom Channels middleware would then be required on the backend to validate this token and populate `scope['user']`. This is not implemented in the current version but is a standard pattern.

---

*This documentation provides a high-level overview. Detailed request/response schemas for each field would typically be generated from the serializers or using tools like Swagger/OpenAPI.*
