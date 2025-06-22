from rest_framework import generics, status, viewsets
from rest_framework.views import APIView # Add APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import UserRegistrationSerializer, UserAPIKeySerializer, UserProfileSerializer
from .models import UserAPIKey # To access EXCHANGE_CHOICES
from rest_framework_simplejwt.views import TokenObtainPairView

class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = (AllowAny,)
    throttle_scope = 'register'

class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_scope = 'login'

class UserAPIKeyViewSet(viewsets.ModelViewSet):
    serializer_class = UserAPIKeySerializer
    permission_classes = [IsAuthenticated]
    throttle_scope = 'api_key_management'

    def get_queryset(self):
        return UserAPIKey.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class ExchangeChoicesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Access choices directly from the model field
        choices = [{'value': choice[0], 'label': choice[1]} for choice in UserAPIKey.EXCHANGE_CHOICES]
        return Response(choices, status=status.HTTP_200_OK)
