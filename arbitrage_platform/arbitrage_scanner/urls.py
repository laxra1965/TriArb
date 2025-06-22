# arbitrage_platform/arbitrage_scanner/urls.py
from django.urls import path
from .views import ArbitrageOpportunitiesView

app_name = 'arbitrage_scanner'

urlpatterns = [
    path('opportunities/', ArbitrageOpportunitiesView.as_view(), name='arbitrage_opportunities'),
]
