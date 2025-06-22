from .models import UserNotification
from django.contrib.auth.models import User
from channels.layers import get_channel_layer # Import
# import asyncio # asyncio might not be directly needed here, asgiref.sync handles it
from asgiref.sync import async_to_sync # Import for calling async from sync code

def create_user_notification(user_instance, message, notification_type='info', related_object=None):
    """
    Helper function to create a UserNotification and send a WebSocket message.
    'related_object' is not implemented in this basic version but shown for future extension.
    """
    if not isinstance(user_instance, User):
        raise TypeError("user_instance must be an instance of django.contrib.auth.models.User")

    notification = UserNotification.objects.create(
        user=user_instance,
        message=message,
        notification_type=notification_type
        # if related_object:
        #     from django.contrib.contenttypes.models import ContentType
        #     notification.content_type = ContentType.objects.get_for_model(related_object)
        #     notification.object_id = related_object.pk
    )

    # Send WebSocket message
    channel_layer = get_channel_layer()
    group_name = f"user_{user_instance.id}_notifications"

    # Prepare message data (similar to what serializer would produce for the new notification)
    message_payload = {
        'type': 'send_notification', # This matches the handler method name in consumer
        'message': { # This is the 'event' dict; 'message' key here is the actual payload for the consumer's handler
            'id': str(notification.id),
            'message': notification.message,
            'notification_type': notification.notification_type,
            'notification_type_display': notification.get_notification_type_display(),
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat(),
            'updated_at': notification.updated_at.isoformat(), # Added updated_at
        }
    }

    # Use async_to_sync to call the async channel_layer.group_send from sync code
    if channel_layer is not None: # Check if channel layer is configured (e.g. not None in tests without full setup)
        async_to_sync(channel_layer.group_send)(group_name, message_payload)

    return notification

# Example usage (would be called from other services):
# from django.contrib.auth.models import User
# user = User.objects.get(username='someuser')
# create_user_notification(user, "Your wallet top-up of $100 has been confirmed.", notification_type='wallet')
# create_user_notification(user, f"Trade attempt {trade_id} completed successfully.", notification_type='trade')
