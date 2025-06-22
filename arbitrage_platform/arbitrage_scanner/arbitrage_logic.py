# arbitrage_platform/arbitrage_scanner/arbitrage_logic.py
import decimal

# Placeholder for EXTREME_PROFIT_THRESHOLD, should be in settings or constants
EXTREME_PROFIT_THRESHOLD = decimal.Decimal('1000.0') # Example %

def find_triangular_arbitrage_opportunities(ticker_map, base_coin="USDT", start_amount=decimal.Decimal('10.0')):
    opportunities = []
    symbols = list(ticker_map.keys()) # Ensure it's a list for iteration
    base_coin_upper = base_coin.upper()

    # Filter symbols to only include those relevant to the base_coin or forming pairs with potential intermediate coins.
    # This is an optimization, but for now, we iterate all symbols and check conditions.

    for pair1_symbol in symbols:
        coin_a = None
        trade1_rate = decimal.Decimal('0')
        trade1_amt_coin_a = decimal.Decimal('0')

        pair1_data = ticker_map.get(pair1_symbol)
        if not pair1_data: continue

        # Leg 1: BaseCoin -> CoinA (BUY CoinA with BaseCoin)
        # Example: pair1_symbol = BTCUSDT. We want to buy BTC using USDT.
        # We need the ask price for BTC/USDT (how much USDT to pay for 1 BTC).
        # Amount of CoinA = StartAmount (USDT) / AskPrice (USDT per CoinA)
        if pair1_symbol.endswith(base_coin_upper):
            potential_coin_a = pair1_symbol[:-len(base_coin_upper)]
            if not potential_coin_a or potential_coin_a == base_coin_upper: continue

            ask_price1 = pair1_data.get('askPrice')
            if not ask_price1 or ask_price1 <= decimal.Decimal('0'): continue

            coin_a = potential_coin_a
            trade1_rate = ask_price1
            trade1_amt_coin_a = start_amount / trade1_rate

        # Consider if BaseCoin is the base of pair1_symbol, e.g. USDTETH for buying ETH with USDT.
        # This means we are selling USDT to get ETH. We'd use the bid price for USDT/ETH.
        # Or, if the pair is ETHUSDT (standard), this path is already covered.
        # The current logic assumes pairs are generally like COIN/BASECOIN or COIN1/COIN2.
        # If pairs like BASECOIN/COIN exist and represent buying COIN with BASECOIN,
        # then we'd use 1 / bid_price_of_BASECOIN_per_COIN.
        # The initial JS logic primarily focused on `pair1.endsWith(baseCoin)`.

        if not coin_a or trade1_amt_coin_a <= decimal.Decimal('0'):
            continue

        for pair2_symbol in symbols:
            if pair1_symbol == pair2_symbol: continue

            coin_b = None
            trade2_rate = decimal.Decimal('0')
            trade2_amt_coin_b = decimal.Decimal('0')
            leg2_action = "" # 'BUY' or 'SELL' (referring to coin_b or coin_a respectively)

            pair2_data = ticker_map.get(pair2_symbol)
            if not pair2_data: continue

            # Leg 2: CoinA -> CoinB
            # Path 2a: Buy CoinB with CoinA. Example: CoinA=BTC, pair2_symbol=ETHBTC. Buy ETH with BTC.
            # We need AskPrice for ETH/BTC. Amount of CoinB = Amount of CoinA / AskPrice (CoinA per CoinB)
            if pair2_symbol.endswith(coin_a):
                potential_coin_b = pair2_symbol[:-len(coin_a)]
                if not potential_coin_b or potential_coin_b == base_coin_upper or potential_coin_b == coin_a: continue

                ask_price2 = pair2_data.get('askPrice')
                if not ask_price2 or ask_price2 <= decimal.Decimal('0'): continue

                coin_b = potential_coin_b
                trade2_rate = ask_price2
                trade2_amt_coin_b = trade1_amt_coin_a / trade2_rate
                leg2_action = f"BUY {coin_b} with {coin_a}"

            # Path 2b: Sell CoinA for CoinB. Example: CoinA=BTC, pair2_symbol=BTCETH. Sell BTC for ETH.
            # We need BidPrice for BTC/ETH. Amount of CoinB = Amount of CoinA * BidPrice (CoinB per CoinA)
            elif pair2_symbol.startswith(coin_a):
                potential_coin_b = pair2_symbol[len(coin_a):]
                if not potential_coin_b or potential_coin_b == base_coin_upper or potential_coin_b == coin_a: continue

                bid_price2 = pair2_data.get('bidPrice')
                if not bid_price2 or bid_price2 <= decimal.Decimal('0'): continue

                coin_b = potential_coin_b
                trade2_rate = bid_price2
                trade2_amt_coin_b = trade1_amt_coin_a * trade2_rate
                leg2_action = f"SELL {coin_a} for {coin_b}"

            if not coin_b or trade2_amt_coin_b <= decimal.Decimal('0'):
                continue

            for pair3_symbol in symbols:
                if pair3_symbol == pair1_symbol or pair3_symbol == pair2_symbol: continue

                final_amount_base_coin = decimal.Decimal('0')
                trade3_rate = decimal.Decimal('0')
                leg3_action = ""

                pair3_data = ticker_map.get(pair3_symbol)
                if not pair3_data: continue

                # Leg 3: CoinB -> BaseCoin (Sell CoinB for BaseCoin)
                # Example: CoinB=ETH, pair3_symbol=ETHUSDT. Sell ETH for USDT.
                # We need BidPrice for ETH/USDT. FinalAmount = Amount of CoinB * BidPrice (USDT per ETH)
                if pair3_symbol.startswith(coin_b) and pair3_symbol.endswith(base_coin_upper):
                    bid_price3 = pair3_data.get('bidPrice')
                    if not bid_price3 or bid_price3 <= decimal.Decimal('0'): continue

                    final_amount_base_coin = trade2_amt_coin_b * bid_price3
                    trade3_rate = bid_price3
                    leg3_action = f"SELL {coin_b} for {base_coin_upper}"

                # Alternative for Leg 3: BaseCoin is base of pair, e.g. USDTETH (Sell ETH for USDT)
                # This implies buying USDT with ETH. We need AskPrice for USDT/ETH (ETH per USDT)
                # FinalAmount = Amount of CoinB / AskPrice (ETH per USDT)
                elif pair3_symbol.startswith(base_coin_upper) and pair3_symbol.endswith(coin_b):
                    ask_price3 = pair3_data.get('askPrice')
                    if not ask_price3 or ask_price3 <= decimal.Decimal('0'): continue

                    final_amount_base_coin = trade2_amt_coin_b / ask_price3 # Amount of ETH / (ETH/USDT) = USDT
                    trade3_rate = ask_price3 # This rate is ETH/USDT, for calculation it's used as divisor
                    leg3_action = f"SELL {coin_b} for {base_coin_upper} (via {pair3_symbol})"


                if final_amount_base_coin <= decimal.Decimal('0'):
                    continue

                profit = final_amount_base_coin - start_amount
                profit_percent = (profit / start_amount) * 100 if start_amount > 0 else decimal.Decimal('0.0')

                if abs(profit_percent) > EXTREME_PROFIT_THRESHOLD:
                    print(f"Extreme profit: {profit_percent:.4f}% for path {pair1_symbol}->{pair2_symbol}->{pair3_symbol}") # Logging

                # Determine action strings for service layer
                action1_service = "BUY"
                action2_service = "BUY" if leg2_action.startswith("BUY") else "SELL"
                action3_service = "SELL"

                op = {
                    'path': [pair1_symbol, pair2_symbol, pair3_symbol],
                    'coins': [base_coin_upper, coin_a, coin_b], # Note: last element is CoinB, not BaseCoin again
                    'start_amount': float(start_amount),
                    'final_amount': float(final_amount_base_coin),
                    'profit': float(profit),
                    'profit_percent': float(profit_percent),
                    'steps_description': [
                        f"BUY {coin_a} with {base_coin_upper} using {pair1_symbol} @ {trade1_rate:.8f}",
                        f"{leg2_action} using {pair2_symbol} @ {trade2_rate:.8f}",
                        f"{leg3_action} using {pair3_symbol} @ {trade3_rate:.8f}"
                    ],
                    'rates': [float(trade1_rate), float(trade2_rate), float(trade3_rate)],
                    'intermediate_amounts': [float(start_amount), float(trade1_amt_coin_a), float(trade2_amt_coin_b), float(final_amount_base_coin)],
                    'actions_for_service': [action1_service, action2_service, action3_service],
                    'base_coin_for_service': base_coin_upper, # The asset we start with for leg 1
                    # For service layer to track assets between legs accurately:
                    # coins_in_trade_path could be [base_coin_upper, coin_a, coin_b, base_coin_upper]
                    # or explicit input/output assets per leg.
                    # Let's add the sequence of assets the trader will hold.
                    'asset_sequence': [base_coin_upper, coin_a, coin_b, base_coin_upper]

                }
                opportunities.append(op)

    opportunities.sort(key=lambda x: x['profit_percent'], reverse=True)
    return opportunities
