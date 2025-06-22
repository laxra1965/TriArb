from rest_framework import serializers
from .models import UserNotification

class UserNotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)

    class Meta:
        model = UserNotification
        fields = ['id', 'message', 'notification_type', 'notification_type_display', 'is_read', 'created_at', 'updated_at'] # Added updated_at
        read_only_fields = ['id', 'message', 'notification_type', 'notification_type_display', 'created_at', 'updated_at']
        # is_read can be updated by the user via a 'mark as read' action through the ViewSet
