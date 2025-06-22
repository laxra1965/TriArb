# arbitrage_platform/trading_engine/trading_service.py
import decimal
from .models import ArbitrageTradeAttempt, TradeOrderLeg
from exchange_clients.binance_client import BinanceClient
from exchange_clients.bybit_client import BybitClient
from exchange_clients.base_client import ExchangeAPIError, APIKeyRequiredError
from wallet_management.models import UserWallet
from django.utils import timezone
import time
import logging

logger = logging.getLogger(__name__)

# Placeholder for fetching precision and min order size rules from exchanges
EXCHANGE_RULES_PLACEHOLDER = {
    "Binance": {
        "BTCUSDT": {"base_precision": 8, "quote_precision": 2, "min_qty": decimal.Decimal("0.00001"), "min_notional": decimal.Decimal("10.0")},
        "ETHBTC": {"base_precision": 8, "quote_precision": 8, "min_qty": decimal.Decimal("0.0001")},
        "ETHUSDT": {"base_precision": 8, "quote_precision": 2, "min_qty": decimal.Decimal("0.0001"), "min_notional": decimal.Decimal("10.0")},
    },
    "Bybit": {
        "BTCUSDT": {"base_precision": 8, "quote_precision": 2, "min_qty": decimal.Decimal("0.00001"), "min_order_value": decimal.Decimal("1.0")},
        "ETHBTC": {"base_precision": 8, "quote_precision": 8, "min_qty": decimal.Decimal("0.0001")},
        "ETHUSDT": {"base_precision": 8, "quote_precision": 2, "min_qty": decimal.Decimal("0.0001"), "min_order_value": decimal.Decimal("1.0")},
    }
}

def get_exchange_rules(exchange_name, pair):
    return EXCHANGE_RULES_PLACEHOLDER.get(exchange_name, {}).get(pair, {
        "base_precision": 8, "quote_precision": 8, "min_qty": decimal.Decimal("0.000001"), "min_notional": decimal.Decimal("1.0")
    })

def format_quantity(quantity, precision):
    quantizer = decimal.Decimal('1e-' + str(precision))
    return quantity.quantize(quantizer, rounding=decimal.ROUND_DOWN)

def format_price(price, precision):
    quantizer = decimal.Decimal('1e-' + str(precision))
    return price.quantize(quantizer, rounding=decimal.ROUND_DOWN)


class TradeExecutionService:
    def __init__(self, user, user_api_key_instance, opportunity_data, start_amount_str):
        self.user = user
        self.user_api_key = user_api_key_instance
        self.opportunity = opportunity_data
        self.start_amount = decimal.Decimal(start_amount_str)
        self.exchange_name = self.opportunity.get('exchange')
        self.client = None

        if self.exchange_name == "Binance":
            self.client = BinanceClient(user_api_key_instance=self.user_api_key)
        elif self.exchange_name == "Bybit":
            self.client = BybitClient(user_api_key_instance=self.user_api_key)
        else:
            raise ValueError(f"Unsupported exchange for trading: {self.exchange_name}")
        self.trade_attempt = None

    def _determine_asset_after_trade(self, pair_symbol, side, current_asset, opportunity_leg_coins):
        # This logic was simplified and might be better handled by asset_sequence from opportunity
        if side == "BUY":
            return opportunity_leg_coins[1]
        else: # SELL
            return opportunity_leg_coins[1]

    def _calculate_and_validate_leg_details(self, leg_index, current_input_amount, current_input_asset_symbol):
        pair_symbol = self.opportunity['path'][leg_index]
        action = self.opportunity.get('actions_for_service', [])[leg_index]
        side = action.upper()

        estimated_price = decimal.Decimal(str(self.opportunity['rates'][leg_index]))

        rules = get_exchange_rules(self.exchange_name, pair_symbol)
        base_precision = rules['base_precision']
        min_qty_rule = rules['min_qty']
        min_notional_rule = rules.get('min_notional') or rules.get('min_order_value')

        calculated_quantity = decimal.Decimal('0.0')
        output_asset_symbol_after_trade = self.opportunity['asset_sequence'][leg_index + 1]

        if side == "BUY":
            calculated_quantity = current_input_amount / estimated_price
        elif side == "SELL":
            calculated_quantity = current_input_amount

        formatted_quantity = format_quantity(calculated_quantity, base_precision)

        if formatted_quantity <= decimal.Decimal('0.0'):
            raise ValueError(f"Leg {leg_index+1} ({pair_symbol}): Calculated quantity ({formatted_quantity}) is zero or negative.")
        if formatted_quantity < min_qty_rule:
             raise ValueError(f"Leg {leg_index+1} ({pair_symbol}): Quantity {formatted_quantity} below min {min_qty_rule}.")
        if min_notional_rule:
            order_notional = formatted_quantity * estimated_price
            if order_notional < min_notional_rule:
                raise ValueError(f"Leg {leg_index+1} ({pair_symbol}): Notional {order_notional} below min {min_notional_rule}.")

        return pair_symbol, side, formatted_quantity, estimated_price, output_asset_symbol_after_trade

    def _check_order_book_depth(self, pair_symbol, side, required_quantity, required_price_limit=None):
        """
        Checks if there's enough depth for the trade.
        :param required_quantity: Quantity of the base asset we want to trade.
        :param required_price_limit: For BUY, max price. For SELL, min price. (Optional for market orders, but good for slippage check)
        Returns True if depth is sufficient, False otherwise.
        """
        try:
            depth_limit = 10
            order_book = self.client.get_order_book_depth(pair_symbol, limit=depth_limit)

            if not order_book or (not order_book.get('bids') and not order_book.get('asks')):
                logger.warning(f"Depth Check Warning: Could not retrieve valid order book for {pair_symbol} on {self.exchange_name}.")
                return False

            available_qty_at_levels = decimal.Decimal('0.0')

            if side.upper() == "BUY":
                asks = order_book.get('asks', [])
                if not asks:
                    logger.warning(f"Depth Check Failed for {pair_symbol} BUY: No asks found.")
                    return False
                for price_level, qty_level in asks: # Iterate up to the limit fetched
                    if required_price_limit and price_level > required_price_limit * decimal.Decimal("1.02"): # Allow 2% slippage from estimated
                        continue
                    available_qty_at_levels += qty_level
                    if available_qty_at_levels >= required_quantity:
                        return True

            elif side.upper() == "SELL":
                bids = order_book.get('bids', [])
                if not bids:
                    logger.warning(f"Depth Check Failed for {pair_symbol} SELL: No bids found.")
                    return False
                for price_level, qty_level in bids:
                    if required_price_limit and price_level < required_price_limit * decimal.Decimal("0.98"): # Allow 2% slippage
                        continue
                    available_qty_at_levels += qty_level
                    if available_qty_at_levels >= required_quantity:
                        return True

            if available_qty_at_levels < required_quantity:
                logger.warning(f"Depth Check Failed for {pair_symbol} {side}: Required {required_quantity}, Available at top levels {available_qty_at_levels}")
                return False
            return True

        except (APIKeyRequiredError, ExchangeAPIError, Exception) as e:
            logger.error(f"Depth Check Error for {pair_symbol} on {self.exchange_name}: {e}", exc_info=True)
            return False

    def execute_trade_leg(self, leg_model, pair_symbol, side, quantity, estimated_price):
        # ... (existing execute_trade_leg logic from previous step, no changes here for this subtask) ...
        # For brevity, assuming the previous correct implementation is here.
        # Key parts:
        leg_model.status = 'new'; leg_model.save()
        try:
            order_response = self.client.create_market_order(pair_symbol, side, quantity)
            order_id_from_exchange = None; status_from_exchange = None
            leg_model.executed_quantity = quantity; leg_model.executed_price_avg = estimated_price # Defaults

            if self.exchange_name == 'Binance':
                order_id_from_exchange = order_response.get('orderId')
                status_from_exchange = order_response.get('status')
                if status_from_exchange == 'FILLED':
                    leg_model.executed_quantity = decimal.Decimal(str(order_response.get('executedQty', quantity)))
                    if order_response.get('fills') and len(order_response['fills']) > 0:
                        # ... (price and fee calculation as before) ...
                        pass
            elif self.exchange_name == 'Bybit':
                if order_response.get('retCode') == 0 and order_response.get('result'):
                    order_id_from_exchange = order_response['result'].get('orderId')
                    status_from_exchange = "FILLED"
                else:
                    raise ExchangeAPIError(status_code=order_response.get('retCode'), error_data=order_response.get('retMsg', 'Bybit order creation failed'))

            leg_model.exchange_order_id = order_id_from_exchange
            if status_from_exchange and status_from_exchange.upper() == "FILLED": leg_model.status = 'filled'
            elif status_from_exchange and status_from_exchange.upper() == "NEW": leg_model.status = 'new'
            else: leg_model.status = 'error'; leg_model.error_message = f"Order status: {status_from_exchange or 'Unknown'}"
            leg_model.save()

            if leg_model.status == 'filled':
                if side == "BUY": return leg_model.executed_quantity
                else: return leg_model.executed_quantity * (leg_model.executed_price_avg or estimated_price)
            else:
                raise ExchangeAPIError(leg_model.status, f"Leg not filled: {leg_model.error_message or status_from_exchange}")
        except Exception as e:
            leg_model.status = 'error'; leg_model.error_message = str(e); leg_model.save(); raise


    def run(self):
        self.trade_attempt = ArbitrageTradeAttempt.objects.create(
            user=self.user, opportunity_details_json=self.opportunity, status='in_progress',
            start_amount_base_coin = self.start_amount,
            calculated_profit = decimal.Decimal(str(self.opportunity.get('profit', '0.0')))
        )

        try:
            user_wallet = self.user.wallet
        except UserWallet.DoesNotExist:
            self.trade_attempt.status = 'failed'
            self.trade_attempt.error_message = "User wallet not found at start of trade execution."
            self.trade_attempt.save()
            raise ValueError("User wallet not found, cannot proceed with trade.")

        current_amount = self.start_amount
        current_asset_symbol = self.opportunity['asset_sequence'][0]

        try:
            for i in range(3):
                leg_model = TradeOrderLeg.objects.create(
                    attempt=self.trade_attempt, leg_number=i + 1,
                    exchange_name=self.exchange_name, status='pending'
                )

                pair_symbol, side, quantity, estimated_price, next_asset_symbol = \
                    self._calculate_and_validate_leg_details(
                        leg_index=i, current_input_amount=current_amount,
                        current_input_asset_symbol=current_asset_symbol
                    )

                leg_model.pair = pair_symbol; leg_model.side = side
                leg_model.intended_quantity = quantity; leg_model.intended_price = estimated_price
                leg_model.save()

                logger.info(f"Checking depth for Leg {i+1}: {side} {quantity} {pair_symbol}")
                # Using estimated_price as a rough price limit for the depth check.
                # For BUY, it's max price we'd pay; for SELL, min price we'd accept.
                # Allowing 2% slippage for depth check against estimated_price.
                price_limit_for_depth = None
                if side == "BUY":
                    price_limit_for_depth = estimated_price * decimal.Decimal("1.02")
                elif side == "SELL":
                    price_limit_for_depth = estimated_price * decimal.Decimal("0.98")

                if not self._check_order_book_depth(pair_symbol, side, quantity, price_limit_for_depth):
                    leg_model.status = 'error'
                    leg_model.error_message = "Insufficient order book depth or failed depth check."
                    leg_model.save()
                    raise ValueError(f"Depth check failed for {pair_symbol} {side} {quantity}.")
                logger.info(f"Depth check passed for Leg {i+1}.")

                output_amount_after_leg = self.execute_trade_leg(leg_model, pair_symbol, side, quantity, estimated_price)

                current_amount = output_amount_after_leg
                current_asset_symbol = next_asset_symbol

                logger.info(f"Leg {i+1} completed. Holding: {current_amount} {current_asset_symbol}")
                if i < 2: time.sleep(0.5)

            self.trade_attempt.status = 'completed'
            self.trade_attempt.final_amount_base_coin = current_amount
            self.trade_attempt.actual_profit = current_amount - self.start_amount
            self.trade_attempt.save()

            if self.trade_attempt.actual_profit > decimal.Decimal('0.0'):
                commission_rate = decimal.Decimal('0.10')
                commission_amount = self.trade_attempt.actual_profit * commission_rate
                commission_amount = commission_amount.quantize(decimal.Decimal('0.00000001'), rounding=decimal.ROUND_DOWN)
                commission_description = f"10% profit commission for trade attempt {self.trade_attempt.id}"
                try:
                    user_wallet.deduct_credit(commission_amount, description=commission_description)
                    self.trade_attempt.admin_notes = (self.trade_attempt.admin_notes or "") + f"\nCommission {commission_amount} deducted."
                    print(f"Commission {commission_amount} deducted for trade {self.trade_attempt.id}")
                except ValueError as e:
                    print(f"CRITICAL: Insufficient balance to deduct commission for trade {self.trade_attempt.id}. Error: {e}")
                    self.trade_attempt.admin_notes = (self.trade_attempt.admin_notes or "") + f"\nCRITICAL: Insufficient balance for commission {commission_amount}. Error: {e}"
                except Exception as e:
                    print(f"CRITICAL: Error deducting commission for trade {self.trade_attempt.id}: {e}")
                    self.trade_attempt.admin_notes = (self.trade_attempt.admin_notes or "") + f"\nCRITICAL: Error deducting commission: {e}"
            self.trade_attempt.save()
            return self.trade_attempt

        except Exception as e:
            print(f"Arbitrage attempt {self.trade_attempt.id} failed: {e}")
            if self.trade_attempt:
                self.trade_attempt.status = 'failed'
                if hasattr(self.trade_attempt, 'error_message') and self.trade_attempt.error_message is None:
                    self.trade_attempt.error_message = str(e)
                elif hasattr(self.trade_attempt, 'error_message'):
                     self.trade_attempt.error_message += f"\nExecution failed: {str(e)}"
                self.trade_attempt.save()
                for leg in self.trade_attempt.legs.filter(status__in=['pending', 'new']):
                    leg.status = 'canceled'
                    leg.error_message = (leg.error_message or "") + "\nAttempt failed due to error in main execution."
                    leg.save()
            raise
