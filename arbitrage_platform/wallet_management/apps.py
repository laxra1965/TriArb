from django.apps import AppConfig


class WalletManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wallet_management'

    def ready(self):
        import wallet_management.models # or specific signal module
