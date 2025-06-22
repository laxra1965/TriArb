from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ArbitrageTradeAttempt, TradeOrderLeg
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
# import json # Not strictly needed if serializing to dict first then json.dumps in consumer

def serialize_trade_leg(instance: TradeOrderLeg):
    return {
        'id': instance.id, # Keep UUID as UUID for internal, consumer can stringify if needed for JSON
        'attempt_id': str(instance.attempt_id),
        'leg_number': instance.leg_number,
        'exchange_name': instance.exchange_name,
        'pair': instance.pair,
        'side': instance.side,
        'side_display': instance.get_side_display(),
        'intended_quantity': str(instance.intended_quantity) if instance.intended_quantity else None,
        'intended_price': str(instance.intended_price) if instance.intended_price else None,
        'executed_quantity': str(instance.executed_quantity) if instance.executed_quantity else None,
        'executed_price_avg': str(instance.executed_price_avg) if instance.executed_price_avg else None,
        'exchange_order_id': instance.exchange_order_id,
        'status': instance.status,
        'status_display': instance.get_status_display(),
        'fee_amount': str(instance.fee_amount) if instance.fee_amount else None,
        'fee_currency': instance.fee_currency,
        'error_message': instance.error_message,
        'created_at': instance.created_at.isoformat() if instance.created_at else None,
        'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
    }

def serialize_trade_attempt(instance: ArbitrageTradeAttempt):
    return {
        'id': str(instance.id),
        'user_id': instance.user_id,
        'status': instance.status,
        'status_display': instance.get_status_display(),
        'opportunity_details': instance.opportunity_details_json,
        'start_amount_base_coin': str(instance.start_amount_base_coin) if instance.start_amount_base_coin else None,
        'final_amount_base_coin': str(instance.final_amount_base_coin) if instance.final_amount_base_coin else None,
        'calculated_profit': str(instance.calculated_profit) if instance.calculated_profit else None,
        'actual_profit': str(instance.actual_profit) if instance.actual_profit else None,
        'commission_deducted': str(instance.commission_deducted) if instance.commission_deducted else None,
        'error_message': instance.error_message,
        'admin_notes': instance.admin_notes,
        'created_at': instance.created_at.isoformat() if instance.created_at else None,
        'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'legs': [serialize_trade_leg(leg) for leg in instance.legs.all().order_by('leg_number')]
    }


@receiver(post_save, sender=ArbitrageTradeAttempt)
def broadcast_trade_attempt_update(sender, instance: ArbitrageTradeAttempt, created, **kwargs):
    channel_layer = get_channel_layer()
    group_name = f"user_{instance.user.id}_trades"
    message_payload = {
        'type': 'send_trade_update',
        'message': {
            'event_type': 'trade_attempt_update',
            'data': serialize_trade_attempt(instance)
        }
    }
    if channel_layer is not None:
        async_to_sync(channel_layer.group_send)(group_name, message_payload)

@receiver(post_save, sender=TradeOrderLeg)
def broadcast_trade_leg_update(sender, instance: TradeOrderLeg, created, **kwargs):
    channel_layer = get_channel_layer()
    # Ensure user object is accessible; instance.attempt.user should work.
    if instance.attempt and hasattr(instance.attempt, 'user') and instance.attempt.user:
        group_name = f"user_{instance.attempt.user.id}_trades"
        message_payload = {
            'type': 'send_trade_update',
            'message': {
                'event_type': 'trade_leg_update',
                'data': serialize_trade_leg(instance)
            }
        }
        if channel_layer is not None:
            async_to_sync(channel_layer.group_send)(group_name, message_payload)
    else:
        # Handle case where leg might somehow not have a user-associated attempt (should not happen)
        print(f"Warning: TradeOrderLeg {instance.id} has no associated user for WebSocket broadcast.")
