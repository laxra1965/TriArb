from rest_framework import serializers
from .models import ArbitrageTradeAttempt, TradeOrderLeg

class TradeOrderLegSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    side_display = serializers.CharField(source='get_side_display', read_only=True)
    class Meta:
        model = TradeOrderLeg
        fields = '__all__' # Or specify fields needed by frontend

class ArbitrageTradeAttemptSerializer(serializers.ModelSerializer):
    legs = TradeOrderLegSerializer(many=True, read_only=True) # Nest legs
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    class Meta:
        model = ArbitrageTradeAttempt
        fields = '__all__' # Or specify fields
