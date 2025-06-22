from django.contrib.auth.models import User
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError # Keep for UserRegistrationSerializer
from .models import UserAPIKey
from wallet_management.models import UserWallet # Import UserWallet
from wallet_management.serializers import UserWalletSerializer # Assuming a simple serializer for UserWallet

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label="Confirm password")

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name')
        extra_kwargs = {
            'email': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        if not attrs.get('email'):
             raise serializers.ValidationError({"email": "Email is required."})
        if User.objects.filter(email=attrs['email']).exists():
             raise serializers.ValidationError({"email": "Email already exists."})
        if User.objects.filter(username=attrs['username']).exists():
             raise serializers.ValidationError({"username": "Username already exists."})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

class UserAPIKeySerializer(serializers.ModelSerializer):
    api_secret = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    _api_secret_encrypted = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = UserAPIKey
        fields = ['id', 'user', 'exchange_name', 'api_key', 'api_secret', '_api_secret_encrypted', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', '_api_secret_encrypted']

    def create(self, validated_data):
        user_api_key = UserAPIKey.objects.create(**validated_data)
        return user_api_key

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('api_secret', None)
        return representation

class UserProfileSerializer(serializers.ModelSerializer):
    wallet = UserWalletSerializer(read_only=True) # Nest wallet details

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'wallet', 'date_joined', 'last_login']
        read_only_fields = ['id', 'username', 'email', 'date_joined', 'last_login', 'wallet']
        # Make email readonly as well, typically not changed here. Username is usually fixed too.
        # For this task, keeping email in fields but as read_only.
        # If email change is needed, a separate endpoint/serializer is better.
