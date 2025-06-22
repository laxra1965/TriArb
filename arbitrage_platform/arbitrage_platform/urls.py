"""
URL configuration for arbitrage_platform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django_otp.admin import OTPAdminSite
from .views import health_check # Import health_check view

# Patch the default admin site to use OTPAdminSite
# This needs to happen before admin.autodiscover() is implicitly called by admin.site.urls
if not isinstance(admin.site, OTPAdminSite):
    admin.site.__class__ = OTPAdminSite

urlpatterns = [
    path("admin/", admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')), # Django's session auth
    path('api/auth/', include('key_management.urls')), # From previous steps
    path('api/scanner/', include('arbitrage_scanner.urls')),
    path('api/trading/', include('trading_engine.urls')),
    path('api/wallet/', include('wallet_management.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('healthz/', health_check, name='health_check'), # Add this line
]
