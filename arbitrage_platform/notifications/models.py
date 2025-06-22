from django.db import models
from django.contrib.auth.models import User
import uuid
# from django.contrib.contenttypes.fields import GenericForeignKey
# from django.contrib.contenttypes.models import ContentType

class UserNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('info', 'Informational'),
        ('wallet', 'Wallet Update'),
        ('trade', 'Trade Update'),
        ('system', 'System Alert'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    is_read = models.BooleanField(default=False)

    # Optional: Link to a relevant object if applicable (e.g., a trade attempt, a deposit request)
    # content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE)
    # object_id = models.PositiveIntegerField(null=True, blank=True)
    # related_object = GenericForeignKey('content_type', 'object_id')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) # Added this field

    class Meta:
        verbose_name = "User Notification"
        verbose_name_plural = "User Notifications"
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:50]}... ({'Read' if self.is_read else 'Unread'})"
