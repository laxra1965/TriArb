import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack # For Django auth in WebSockets
# Import routing from your apps
import notifications.routing
import wallet_management.routing # New
import trading_engine.routing    # New

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arbitrage_platform.settings')

# Get the default Django ASGI application to handle HTTP requests
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack( # AuthMiddlewareStack enables session/user access
        URLRouter([
            *notifications.routing.websocket_urlpatterns,
            *wallet_management.routing.websocket_urlpatterns,
            *trading_engine.routing.websocket_urlpatterns,
        ])
    ),
})
