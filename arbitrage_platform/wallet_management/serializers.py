from rest_framework import serializers
from .models import UserWallet, WalletTransaction, WalletDepositRequest
from django.contrib.auth.models import User
import decimal

class UserWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserWallet
        fields = ['balance', 'updated_at']

class WalletTransactionSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    class Meta:
        model = WalletTransaction
        fields = ['id', 'wallet', 'transaction_type', 'transaction_type_display', 'amount', 'timestamp', 'description']
        # Wallet field will show UserWallet ID. For more detail, consider:
        # wallet = UserWalletSerializer()
        # Or a simpler StringRelatedField for user:
        # wallet_user = serializers.StringRelatedField(source='wallet.user.username')


class WalletDepositRequestSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = WalletDepositRequest
        fields = ['id', 'user', 'amount_requested', 'currency', 'status', 'status_display', 'created_at', 'blockchain_tx_id']
        read_only_fields = ['id', 'user', 'currency', 'status', 'status_display', 'created_at']

class CreateWalletDepositRequestSerializer(serializers.ModelSerializer):
    amount_requested = serializers.DecimalField(max_digits=19, decimal_places=8, min_value=decimal.Decimal('0.01'))
    blockchain_tx_id = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = WalletDepositRequest
        fields = ['amount_requested', 'blockchain_tx_id']

    def validate_amount_requested(self, value):
        if value < decimal.Decimal('1.00'):
            raise serializers.ValidationError("Minimum deposit amount is $1.00 USDT.")
        if value > decimal.Decimal('10000.00'):
            raise serializers.ValidationError("Maximum deposit amount per request is $10,000.00 USDT.")
        return value
