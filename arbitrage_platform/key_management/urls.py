from django.urls import path, include
from .views import UserRegistrationView, UserAPIKeyViewSet, UserProfileView, CustomTokenObtainPairView, ExchangeChoicesView # Add ExchangeChoicesView
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from rest_framework.routers import DefaultRouter

app_name = 'key_management' # As set previously

router = DefaultRouter()
router.register(r'keys', UserAPIKeyViewSet, basename='userapikey')

urlpatterns = [
    # Auth URLs
    path('register/', UserRegistrationView.as_view(), name='user_register'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'), # Use custom view
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('users/me/', UserProfileView.as_view(), name='user_profile'),
    path('exchange-choices/', ExchangeChoicesView.as_view(), name='exchange_choices'), # Add this line
    # New URLs for API Key Management, router generates CRUD paths for 'keys'
    path('', include(router.urls)),
]
