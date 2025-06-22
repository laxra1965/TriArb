# arbitrage_platform/wallet_management/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WalletDepositRequestViewSet, WalletTransactionViewSet # Import new ViewSet

app_name = 'wallet_management'
router = DefaultRouter()
router.register(r'deposit-requests', WalletDepositRequestViewSet, basename='walletdepositrequest')
router.register(r'transactions', WalletTransactionViewSet, basename='wallettransaction') # Add this line

urlpatterns = [
    path('', include(router.urls)),
]
