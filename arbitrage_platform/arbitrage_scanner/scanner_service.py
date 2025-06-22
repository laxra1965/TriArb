# arbitrage_platform/arbitrage_scanner/scanner_service.py
import decimal
from .exchange_config import EXCHANGE_API_CONFIG
from .arbitrage_logic import find_triangular_arbitrage_opportunities
from .scanner_utils import fetch_exchange_ticker_data, fetch_specific_tickers_data
from market_data.filters import get_liquid_pairs
import logging

logger = logging.getLogger(__name__)

def scan_for_arbitrage(selected_exchanges=None, base_coin="USDT", start_amount_str="10.0",
                           user_api_key_instances=None, version="v1"):
    """
    Orchestrates the arbitrage scanning process.
    Can use V1 (all pairs from config) or V2 (dynamically discovered liquid pairs) logic.
    """
    all_opportunities = []
    start_amount_decimal = decimal.Decimal(start_amount_str)

    if selected_exchanges is None:
        selected_exchanges = list(EXCHANGE_API_CONFIG.keys())

    for exchange_name in selected_exchanges:
        logger.info(f"Processing {exchange_name} for arbitrage (Version: {version})...")

        ticker_map_for_exchange = {}
        current_exchange_key_instance = user_api_key_instances.get(exchange_name) if user_api_key_instances else None

        if version == "v2":
            liquid_pairs_qs = get_liquid_pairs(exchange_name=exchange_name)

            if not liquid_pairs_qs.exists():
                logger.info(f"V2: No liquid pairs found for {exchange_name} after filtering from DB.")
                continue

            ticker_map_for_exchange = fetch_specific_tickers_data(
                exchange_name,
                liquid_pairs_qs,
                user_api_key_instance=current_exchange_key_instance
            )
            if not ticker_map_for_exchange:
                # Use .count() for querysets
                logger.warning(f"V2: Could not fetch specific tickers for {liquid_pairs_qs.count()} liquid pairs on {exchange_name}.")
                continue

        else: # V1 logic
            if exchange_name not in EXCHANGE_API_CONFIG:
                logger.warning(f"V1 Warning: Selected exchange {exchange_name} not in V1 config (EXCHANGE_API_CONFIG).")
                continue

            key_map_for_v1_fetch = {exchange_name: current_exchange_key_instance} if current_exchange_key_instance else None
            ticker_map_for_exchange = fetch_exchange_ticker_data(
                exchange_name,
                user_api_key_instance_map=key_map_for_v1_fetch
            )
            if not ticker_map_for_exchange:
                logger.warning(f"V1: No ticker data fetched for {exchange_name}.")
                continue

        if not ticker_map_for_exchange:
            logger.warning(f"No ticker data available for {exchange_name} for version {version}. Skipping arbitrage calculation.")
            continue

        logger.info(f"Finding opportunities for {exchange_name} with {len(ticker_map_for_exchange)} tickers (Version: {version})...")
        try:
            exchange_opportunities = find_triangular_arbitrage_opportunities(
                ticker_map_for_exchange,
                base_coin=base_coin,
                start_amount=start_amount_decimal
            )
        except Exception as e:
            logger.error(f"Error during arbitrage calculation for {exchange_name} (Version: {version}): {e}", exc_info=True)
            exchange_opportunities = []

        for op in exchange_opportunities:
            op['exchange'] = exchange_name
            op['scanner_version'] = version

        all_opportunities.extend(exchange_opportunities)
        logger.info(f"Found {len(exchange_opportunities)} opportunities on {exchange_name} (Version: {version}).")

    all_opportunities.sort(key=lambda x: x['profit_percent'], reverse=True)
    return all_opportunities
