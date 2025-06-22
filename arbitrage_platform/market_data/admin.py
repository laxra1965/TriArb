from django.contrib import admin
from .models import TrackedExchangePair
from django.utils.html import format_html # For custom display methods

@admin.register(TrackedExchangePair)
class TrackedExchangePairAdmin(admin.ModelAdmin):
    list_display = (
        'exchange_name',
        'symbol',
        'raw_exchange_symbol',
        'base_asset',
        'quote_asset',
        'last_price_display',
        'volume_24h_quote_display',
        'is_active_for_scan',
        'last_volume_update'
    )
    list_filter = ('exchange_name', 'is_active_for_scan', 'quote_asset', 'base_asset')
    search_fields = ('symbol', 'raw_exchange_symbol', 'base_asset', 'quote_asset')
    ordering = ('exchange_name', 'symbol')

    # Allow direct editing of is_active_for_scan in the list view
    list_editable = ('is_active_for_scan',)

    readonly_fields = ('created_at', 'updated_at', 'last_volume_update',
                       'volume_24h_base', 'volume_24h_quote', 'last_price',
                       'precision_rules_json') # Make fetched data readonly

    fieldsets = (
        ("Pair Identity", {
            'fields': ('exchange_name', 'symbol', 'raw_exchange_symbol', 'base_asset', 'quote_asset')
        }),
        ("Activity & Rules", {
            'fields': ('is_active_for_scan', 'precision_rules_json')
        }),
        ("Market Data (updated by tasks)", {
            'fields': ('last_price', 'volume_24h_base', 'volume_24h_quote', 'last_volume_update'),
        }),
        ("Timestamps", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def volume_24h_quote_display(self, obj):
        if obj.volume_24h_quote is not None:
            # Assuming quote_asset is like USDT, BUSD, etc. where 2 decimal places for currency value is common
            return f"{obj.volume_24h_quote:,.2f} {obj.quote_asset}"
        return None
    volume_24h_quote_display.short_description = '24h Volume (Quote)'
    volume_24h_quote_display.admin_order_field = 'volume_24h_quote' # Allows sorting by this column

    def last_price_display(self, obj):
        if obj.last_price is not None:
             # Adjust formatting based on typical price magnitudes
            if obj.last_price > 100: # e.g. BTCUSDT
                return f"{obj.last_price:,.2f}"
            elif obj.last_price > 1: # e.g. ETHUSDT
                return f"{obj.last_price:,.4f}"
            else: # e.g. SHIBUSDT or ETHBTC
                return f"{obj.last_price:,.8f}"
        return None
    last_price_display.short_description = 'Last Price'
    last_price_display.admin_order_field = 'last_price' # Allows sorting by this column
