from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserWallet, WalletDepositRequest, WalletTransaction # Add WalletTransaction
from .serializers import WalletDepositRequestSerializer, CreateWalletDepositRequestSerializer, WalletTransactionSerializer # Add WalletTransactionSerializer
from django.conf import settings

class WalletDepositRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return WalletDepositRequest.objects.filter(user=self.request.user).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateWalletDepositRequestSerializer
        return WalletDepositRequestSerializer

    def perform_create(self, serializer):
        status_val = 'pending_confirmation' if serializer.validated_data.get('blockchain_tx_id') else 'pending_user_action'
        serializer.save(user=self.request.user, currency="USDT", status=status_val)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        response_serializer = WalletDepositRequestSerializer(serializer.instance) # Use main serializer for response

        deposit_info = {
            "message": "Deposit request created. Please send funds to the address below if you haven't already.",
            "deposit_address_USDT_TRC20": settings.USDT_TRC20_DEPOSIT_ADDRESS,
            "qr_code_url_USDT_TRC20": settings.USDT_TRC20_QR_CODE_URL,
            "request_details": response_serializer.data
        }
        return Response(deposit_info, status=status.HTTP_201_CREATED, headers=headers)

class WalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]
    # pagination_class = PageNumberPagination # Example if specific pagination needed

    def get_queryset(self):
        # Users can only see transactions for their own wallet
        try:
            # Ensure wallet exists for the user. If not, they wouldn't have transactions anyway.
            user_wallet = UserWallet.objects.get(user=self.request.user)
            return WalletTransaction.objects.filter(wallet=user_wallet).order_by('-timestamp')
        except UserWallet.DoesNotExist:
            return WalletTransaction.objects.none() # Return empty queryset if no wallet
        except Exception: # Catch any other unexpected error during wallet fetch
            # Log this unexpected error
            return WalletTransaction.objects.none()
