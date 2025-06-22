from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import UserNotification
from .serializers import UserNotificationSerializer
from django.utils import timezone # For marking as read

class UserNotificationViewSet(viewsets.ReadOnlyModelViewSet): # ReadOnly for now, with custom actions for modification
    serializer_class = UserNotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own notifications
        queryset = UserNotification.objects.filter(user=self.request.user)

        is_read_param = self.request.query_params.get('is_read')
        if is_read_param is not None:
            if is_read_param.lower() == 'false':
                queryset = queryset.filter(is_read=False)
            elif is_read_param.lower() == 'true':
                queryset = queryset.filter(is_read=True)
        return queryset

    @action(detail=True, methods=['post'], name='Mark as Read')
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        if notification.user != request.user:
            return Response({"error": "Forbidden."}, status=status.HTTP_403_FORBIDDEN) # Should be caught by get_queryset

        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read', 'updated_at'])
        return Response({'status': 'notification marked as read'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], name='Mark All as Read')
    def mark_all_as_read(self, request):
        # Get queryset for the current user (respects initial filtering by user)
        queryset_to_update = self.get_queryset().filter(is_read=False)
        count = queryset_to_update.update(is_read=True, updated_at=timezone.now())
        return Response({'status': f'{count} notifications marked as read'}, status=status.HTTP_200_OK)
