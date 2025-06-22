from django.apps import AppConfig


class TradingEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trading_engine'

    def ready(self):
        import trading_engine.signals # Import signals to connect them
