from django.db import models
import decimal

class TrackedExchangePair(models.Model):
    EXCHANGE_CHOICES = [
        ('Binance', 'Binance'),
        ('Bybit', 'Bybit'),
        # Add other V2 supported exchanges here
        ('OKX', 'OKX'),
        ('KuCoin', 'KuCoin'),
        ('Gate', 'Gate.io'), # Consistent naming with potential display needs
        ('MEXC', 'MEXC'),
        ('HTX', 'HTX'),
        ('Bitget', 'Bitget'),
        ('Bitfinex', 'Bitfinex'),
        ('BingX', 'BingX'),
        # Add more as full client/parser support is added
    ]

    exchange_name = models.CharField(max_length=50, choices=EXCHANGE_CHOICES)
    symbol = models.CharField(max_length=30, help_text="Standardized symbol, e.g., BTCUSDT") # Our standardized symbol
    raw_exchange_symbol = models.CharField(max_length=30, help_text="Symbol as used by the exchange, e.g., BTCUSDT or BTC-USDT")

    base_asset = models.CharField(max_length=20)
    quote_asset = models.CharField(max_length=20)

    # Volume and Price data - updated periodically
    volume_24h_base = models.DecimalField(max_digits=28, decimal_places=8, null=True, blank=True, help_text="24h volume in base asset terms")
    volume_24h_quote = models.DecimalField(max_digits=28, decimal_places=8, null=True, blank=True, help_text="24h volume in quote asset terms (e.g., USDT)")
    last_price = models.DecimalField(max_digits=28, decimal_places=12, null=True, blank=True) # Allow more precision for price
    last_volume_update = models.DateTimeField(null=True, blank=True)

    is_active_for_scan = models.BooleanField(default=True, help_text="Actively scanned for arbitrage if true and meets liquidity criteria")
    # Precision and limit rules from exchange (can be complex)
    # Storing as JSON for flexibility. Could be broken into specific fields if consistently available.
    precision_rules_json = models.JSONField(null=True, blank=True, help_text="Exchange-specific precision rules, lot sizes, etc.")
    # min_trade_size_base = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True, help_text="Minimum trade size in base asset")
    # min_trade_value_quote = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True, help_text="Minimum trade value in quote asset (e.g. minNotional)")


    # Timestamps for the record itself
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('exchange_name', 'symbol') # Our standardized symbol should be unique per exchange
        indexes = [
            models.Index(fields=['exchange_name', 'symbol']),
            models.Index(fields=['is_active_for_scan']),
            models.Index(fields=['quote_asset']), # For filtering by common quote assets
        ]
        verbose_name = "Tracked Exchange Pair"
        verbose_name_plural = "Tracked Exchange Pairs"

    def __str__(self):
        return f"{self.exchange_name} - {self.symbol} (Raw: {self.raw_exchange_symbol})"
