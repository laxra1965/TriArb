from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserNotificationViewSet

app_name = 'notifications'
router = DefaultRouter()
router.register(r'user-notifications', UserNotificationViewSet, basename='usernotification')

urlpatterns = [
    path('', include(router.urls)),
]
