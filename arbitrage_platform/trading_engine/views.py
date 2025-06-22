from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, viewsets # Added viewsets
from .trading_service import TradeExecutionService
from key_management.models import UserAPIKey
from wallet_management.models import UserWallet
import decimal
import logging # Added
from .models import ArbitrageTradeAttempt, TradeOrderLeg
from .serializers import ArbitrageTradeAttemptSerializer, TradeOrderLegSerializer

logger = logging.getLogger(__name__) # Added

class ExecuteTradeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'trade_execute' # Apply 'trade_execute' scope

    def post(self, request, *args, **kwargs):
        user = request.user
        opportunity_data = request.data.get('opportunity')
        start_amount_str = str(request.data.get('start_amount', '10.0'))

        if not opportunity_data:
            return Response(
                {"error": "Opportunity data is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        exchange_name = opportunity_data.get('exchange')
        if not exchange_name:
            return Response(
                {"error": "Exchange name missing in opportunity data."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            wallet = user.wallet
        except UserWallet.DoesNotExist:
            return Response(
                {"error": "User wallet not found. Please contact support."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user_api_key = UserAPIKey.objects.get(user=user, exchange_name=exchange_name)
        except UserAPIKey.DoesNotExist:
            return Response(
                {"error": f"API key for {exchange_name} not found or not configured for this user."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user_api_key.get_api_secret():
             return Response(
                {"error": f"API secret for {exchange_name} is missing, invalid, or could not be decrypted."},
                status=status.HTTP_400_BAD_REQUEST
            )

        trade_service = TradeExecutionService(
            user=user,
            user_api_key_instance=user_api_key,
            opportunity_data=opportunity_data,
            start_amount_str=start_amount_str
        )

        try:
            trade_attempt_instance = trade_service.run()
            return Response({
                "message": "Trade execution process finished.",
                "trade_attempt_id": trade_attempt_instance.id,
                "status": trade_attempt_instance.status,
                "final_amount_base_coin": trade_attempt_instance.final_amount_base_coin,
                "actual_profit": trade_attempt_instance.actual_profit,
                "legs": [{
                    "leg_number": leg.leg_number, "pair": leg.pair, "side": leg.side,
                    "status": leg.status, "exchange_order_id": leg.exchange_order_id,
                    "error_message": leg.error_message
                } for leg in trade_attempt_instance.legs.all()]
            }, status=status.HTTP_200_OK)
        except ValueError as ve:
            return Response({"error": f"Trade execution failed: {str(ve)}"}, status=status.HTTP_400_BAD_REQUEST)
        except APIKeyRequiredError as akre:
             logger.warning(f"API Key error during trade for user {user.username}: {akre}", exc_info=True)
             return Response({"error": f"Trade execution failed due to API key/secret issue: {str(akre)}"}, status=status.HTTP_400_BAD_REQUEST)
        except ExchangeAPIError as eaer:
            logger.error(f"Exchange API error during trade for user {user.username}: {eaer}", exc_info=True)
            return Response(
                {"error": f"Trade execution failed due to an exchange API error: {str(eaer)}. Check trade history for details."},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            logger.critical(f"Critical error during trade execution service run for user {user.username}: {e}", exc_info=True)
            return Response(
                {"error": "A critical error occurred during trade execution. Check trade history for details."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ArbitrageTradeAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ArbitrageTradeAttemptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ArbitrageTradeAttempt.objects.filter(user=self.request.user).order_by('-created_at')

class TradeOrderLegViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TradeOrderLegSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # For non-nested setup, filter by query parameter if provided
        attempt_id = self.request.query_params.get('attempt_id')
        if attempt_id:
            return TradeOrderLeg.objects.filter(
                attempt_id=attempt_id,
                attempt__user=self.request.user # Ensure user owns the parent attempt
            ).order_by('leg_number')
        # If no attempt_id, could return all legs for user, or none.
        # Returning none is safer if specific attempt context is usually expected.
        return TradeOrderLeg.objects.filter(attempt__user=self.request.user).order_by('-attempt__created_at', 'leg_number')
