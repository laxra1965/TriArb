# arbitrage_platform/arbitrage_scanner/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .scanner_service import scan_for_arbitrage
from wallet_management.models import UserWallet
from key_management.models import UserAPIKey
from django.conf import settings
import decimal
import logging # Added

logger = logging.getLogger(__name__) # Added

class ArbitrageOpportunitiesView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'opportunity_scan'

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            wallet = user.wallet
        except UserWallet.DoesNotExist:
            return Response(
                {"error": "User wallet not found. Please contact support."},
                status=status.HTTP_400_BAD_REQUEST
            )

        minimum_balance = getattr(settings, 'MINIMUM_SCANNER_ACCESS_BALANCE', decimal.Decimal('1.0'))
        if wallet.balance < minimum_balance:
            return Response(
                {"message": f"Insufficient balance to view arbitrage opportunities. A minimum of {minimum_balance} USDT (or equivalent) is required."},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        user_keys = UserAPIKey.objects.filter(user=user)
        user_api_key_instances_map = {key.exchange_name: key for key in user_keys}

        exchanges_param = request.query_params.get('exchanges')
        selected_exchanges = None
        if exchanges_param:
            selected_exchanges = [exc.strip() for exc in exchanges_param.split(',')]

        base_coin = request.query_params.get('base_coin', 'USDT')
        start_amount_str = request.query_params.get('start_amount', '10.0')

        # --- Add Version Query Parameter ---
        scanner_version = request.query_params.get('version', 'v1').lower() # Default to 'v1'
        if scanner_version not in ['v1', 'v2']:
            return Response(
                {"error": "Invalid 'version' parameter. Must be 'v1' or 'v2'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # --- End of Version Query Parameter ---

        # Optional: Global toggle for V2 if it's not ready for everyone
        # V2_ENABLED_GLOBALLY = getattr(settings, 'V2_SCANNER_ENABLED', False)
        # if scanner_version == 'v2' and not V2_ENABLED_GLOBALLY:
        #     return Response({"error": "Scanner V2 is not currently available."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            opportunities = scan_for_arbitrage(
                selected_exchanges=selected_exchanges,
                base_coin=base_coin,
                start_amount_str=start_amount_str,
                user_api_key_instances=user_api_key_instances_map,
                version=scanner_version # Pass the version to the service
            )
            return Response(opportunities, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during arbitrage scan (version: {scanner_version}, user: {user.username}): {e}", exc_info=True)
            return Response(
                {"error": "An error occurred while scanning for opportunities. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
