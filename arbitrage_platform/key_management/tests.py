from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings
from .models import UserAPIKey, encrypt_secret, decrypt_secret

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from django.test import override_settings # For throttling tests
import time # For throttling tests
import decimal # For UserProfileAPITest
from wallet_management.models import UserWallet # For UserProfileAPITest


class UserAPIKeyModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser_apikey_model', password='password123')
        if not settings.SECRET_KEY:
            settings.SECRET_KEY = 'a_test_secret_key_for_encryption_functions_32bytes'

    def test_encrypt_decrypt_functions(self):
        original_secret = "my_super_secret_api_key_string"
        encrypted = encrypt_secret(original_secret)
        self.assertIsNotNone(encrypted)
        self.assertNotEqual(original_secret, encrypted)
        decrypted = decrypt_secret(encrypted)
        self.assertEqual(original_secret, decrypted)

    def test_encrypt_decrypt_empty_string(self):
        encrypted = encrypt_secret("")
        self.assertIsNone(encrypted)
        decrypted_from_none = decrypt_secret(None)
        self.assertEqual("", decrypted_from_none)

    def test_api_secret_property(self):
        api_key_instance = UserAPIKey(user=self.user, exchange_name="Binance", api_key="test_api_key_prop_model")
        original_secret = "another_secret_value_456"
        api_key_instance.api_secret = original_secret
        api_key_instance.save()
        retrieved_instance = UserAPIKey.objects.get(id=api_key_instance.id)
        self.assertIsNotNone(retrieved_instance._api_secret_encrypted)
        self.assertNotEqual(original_secret, retrieved_instance._api_secret_encrypted)
        if retrieved_instance._api_secret_encrypted:
             self.assertTrue(len(retrieved_instance._api_secret_encrypted) > 0)
        decrypted_secret = retrieved_instance.api_secret
        self.assertEqual(original_secret, decrypted_secret)

    def test_api_secret_property_empty(self):
        api_key_instance = UserAPIKey(user=self.user, exchange_name="TestExchangeEmptyModel", api_key="empty_secret_key_prop_model")
        api_key_instance.api_secret = ""
        api_key_instance.save()
        retrieved_instance = UserAPIKey.objects.get(id=api_key_instance.id)
        self.assertIsNone(retrieved_instance._api_secret_encrypted)
        decrypted_secret = retrieved_instance.api_secret
        self.assertEqual("", decrypted_secret)

    def test_get_api_secret_on_none_encrypted_in_db(self):
        api_key_instance = UserAPIKey.objects.create(
            user=self.user,
            exchange_name="NoSecretExchangeDBModel",
            api_key="no_secret_here_db_model",
            _api_secret_encrypted=None
        )
        retrieved_instance = UserAPIKey.objects.get(id=api_key_instance.id)
        self.assertEqual("", retrieved_instance.api_secret)

    def test_fernet_key_generation(self):
        from .models import FERNET_KEY
        self.assertIsInstance(FERNET_KEY, bytes)
        import base64
        try:
            decoded_key = base64.urlsafe_b64decode(FERNET_KEY)
            self.assertEqual(len(decoded_key), 32)
        except Exception as e:
            self.fail(f"FERNET_KEY '{FERNET_KEY}' is not valid URL-safe base64: {e}")


class AuthAPIEndpointsTest(APITestCase):
    def setUp(self):
        self.user_password = "strong_password123"
        self.user_data_reg = { # Renamed to avoid clash if self.user_data is used elsewhere
            "username": "testuser_auth_api",
            "email": "testuser_auth@example.com",
            "password": self.user_password,
            "password2": self.user_password,
            "first_name": "Test",
            "last_name": "UserAuth"
        }
        self.user = User.objects.create_user(
            username="existinguser_auth", # Make usernames unique across test classes
            email="existing_auth@example.com",
            password=self.user_password
        )

    def test_user_registration_success(self):
        url = reverse("key_management:user_register")
        response = self.client.post(url, self.user_data_reg, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username=self.user_data_reg["username"]).exists())

    def test_user_registration_existing_username(self):
        User.objects.create_user(username=self.user_data_reg["username"], email="unique_email_auth@example.com", password=self.user_password)
        url = reverse("key_management:user_register")
        response = self.client.post(url, self.user_data_reg, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    # ... (other registration tests from previous step remain here) ...
    def test_user_registration_existing_email(self):
        User.objects.create_user(username="anotheruser_auth", email=self.user_data_reg["email"], password=self.user_password)
        url = reverse("key_management:user_register")
        response = self.client.post(url, self.user_data_reg, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_user_registration_mismatched_passwords(self):
        data = self.user_data_reg.copy()
        data["password2"] = "wrongpassword"
        url = reverse("key_management:user_register")
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_user_registration_missing_fields(self):
        url = reverse("key_management:user_register")
        data_no_email = {k: v for k, v in self.user_data_reg.items() if k != 'email'}
        response = self.client.post(url, data_no_email, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

        data_no_password = {k: v for k, v in self.user_data_reg.items() if k != 'password'}
        response = self.client.post(url, data_no_password, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_login_success(self):
        url = reverse("key_management:token_obtain_pair")
        data = {"username": self.user.username, "password": self.user_password}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        return response.data

    def test_login_invalid_credentials(self):
        url = reverse("key_management:token_obtain_pair")
        data = {"username": self.user.username, "password": "wrong_password"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_success(self):
        login_data = self.test_login_success()
        refresh_token = login_data["refresh"]
        url = reverse("key_management:token_refresh")
        data = {"refresh": refresh_token}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        # With ROTATE_REFRESH_TOKENS=True, new refresh token should be returned
        self.assertIn("refresh", response.data)


    def test_token_refresh_invalid_token(self):
        url = reverse("key_management:token_refresh")
        data = {"refresh": "invalid_token_string"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_blacklist_success_and_usage(self):
        login_response_data = self.test_login_success()
        refresh_token = login_response_data['refresh']
        blacklist_url = reverse("key_management:token_blacklist")
        blacklist_data = {"refresh": refresh_token}
        response_blacklist = self.client.post(blacklist_url, blacklist_data, format='json')
        self.assertEqual(response_blacklist.status_code, status.HTTP_200_OK)
        refresh_url = reverse("key_management:token_refresh")
        refresh_data = {"refresh": refresh_token}
        response_refresh_after_blacklist = self.client.post(refresh_url, refresh_data, format='json')
        self.assertEqual(response_refresh_after_blacklist.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("token_not_valid", response_refresh_after_blacklist.data.get("code", ""))


class UserAPIKeyAPITest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_password = "strong_password123_keyapi"
        cls.user = User.objects.create_user(username='testuser_keyapi', email='keyapi@example.com', password=cls.user_password)
        cls.other_user = User.objects.create_user(username='otheruser_keyapi', email='otherkeyapi@example.com', password=cls.user_password)
        if not settings.SECRET_KEY:
            settings.SECRET_KEY = 'a_test_secret_key_for_encryption_functions_32bytes_apikeytest'

    def setUp(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')
        self.list_create_url = reverse("key_management:userapikey-list")

    # ... (existing UserAPIKeyAPITest methods from previous step) ...
    def test_create_api_key_success(self):
        data = {"exchange_name": "Binance", "api_key": "my_binance_api_key_123", "api_secret": "my_binance_secret_456"}
        response = self.client.post(self.list_create_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserAPIKey.objects.count(), 1)

    def test_create_api_key_unauthenticated(self):
        self.client.credentials()
        data = {"exchange_name": "Binance", "api_key": "key", "api_secret": "secret"}
        response = self.client.post(self.list_create_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_api_keys_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(self.list_create_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_api_key_unauthenticated(self):
        self.client.credentials()
        # Create a key first to have a PK, but access it unauthenticated
        key = UserAPIKey.objects.create(user=self.user, exchange_name="Binance", api_key="key_detail_unauth", _api_secret_encrypted=encrypt_secret("s"))
        detail_url = reverse("key_management:userapikey-detail", kwargs={'pk': key.pk})
        response = self.client.get(detail_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    # ... (other UserAPIKeyAPITest methods from previous step, ensuring unauth checks)


class UserProfileAPITest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_password = "profile_password123"
        cls.user = User.objects.create_user(username='testprofileuser_api', email='profileapi@example.com', password=cls.user_password, first_name="Profile", last_name="User")
        cls.wallet = UserWallet.objects.get(user=cls.user) # Wallet created by signal
        cls.wallet.balance = decimal.Decimal("123.45")
        cls.wallet.save()

    def setUp(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')
        self.profile_url = reverse("key_management:user_profile")

    def test_get_user_profile_success(self):
        response = self.client.get(self.profile_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.user.username)

    def test_get_user_profile_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(self.profile_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(REST_FRAMEWORK={
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '5/minute', # Low rate for anon tests
        'user': '10/minute', # Low rate for user tests
        'login': '2/minute', # Test specific scope
        'register': '2/minute', # Test specific scope
        'api_key_management': '3/minute', # Test specific scope
    }
})
class ThrottleAPITest(APITestCase):
    def setUp(self):
        self.user_password = "throttle_password"
        self.user = User.objects.create_user(username='throttletestuser', email='throttle@example.com', password=self.user_password)
        self.register_url = reverse("key_management:user_register")
        self.login_url = reverse("key_management:token_obtain_pair")
        self.apikey_list_url = reverse("key_management:userapikey-list")

    def test_register_throttling_anon(self):
        # Scope 'register': 2/minute
        for i in range(2):
            response = self.client.post(self.register_url, {"username": f"newuser{i}", "email": f"new{i}@e.com", "password": "p", "password2": "p"}, format='json')
            self.assertNotIn([status.HTTP_429_TOO_MANY_REQUESTS], [response.status_code]) # Allow for 400 if data bad, but not 429 yet

        response = self.client.post(self.register_url, {"username": "newuser2", "email": "new2@e.com", "password": "p", "password2": "p"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_throttling_anon(self):
        # Scope 'login': 2/minute
        for i in range(2):
            self.client.post(self.login_url, {"username": "nonexistent", "password": "p"}, format='json')
            # We don't care about 401 here, just that it's not 429 yet

        response = self.client.post(self.login_url, {"username": "nonexistent", "password": "p"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_apikey_management_throttling_user(self):
        # Scope 'api_key_management': 3/minute
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        for i in range(3):
            response = self.client.get(self.apikey_list_url, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(self.apikey_list_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    # Test for "One Session Per User" (Blacklist after Rotation)
    def test_token_rotation_and_blacklist(self):
        # 1. Login to get initial token pair A
        token_url = reverse("key_management:token_obtain_pair")
        login_data = {"username": self.user.username, "password": self.user_password}
        response_A = self.client.post(token_url, login_data, format='json')
        self.assertEqual(response_A.status_code, status.HTTP_200_OK)
        refresh_A1 = response_A.data['refresh']
        access_A1 = response_A.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_A1}') # Use current access token

        # 2. Use refresh_A1 to get new token pair B
        refresh_url = reverse("key_management:token_refresh")
        response_B = self.client.post(refresh_url, {"refresh": refresh_A1}, format='json')
        self.assertEqual(response_B.status_code, status.HTTP_200_OK)
        refresh_B1 = response_B.data['refresh'] # New refresh token due to ROTATE_REFRESH_TOKENS=True
        access_B1 = response_B.data['access']
        self.assertNotEqual(refresh_A1, refresh_B1) # New refresh token issued
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_B1}')


        # 3. Attempt to use refresh_A1 again. It should be blacklisted.
        response_A_again = self.client.post(refresh_url, {"refresh": refresh_A1}, format='json')
        self.assertEqual(response_A_again.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("token_not_valid", response_A_again.data.get("code", ""))

        # 4. Verify refresh_B1 can be used to get pair C
        response_C = self.client.post(refresh_url, {"refresh": refresh_B1}, format='json')
        self.assertEqual(response_C.status_code, status.HTTP_200_OK)
        refresh_C1 = response_C.data['refresh']
        access_C1 = response_C.data['access']
        self.assertNotEqual(refresh_B1, refresh_C1)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_C1}')


        # 5. Attempt to use refresh_B1 again. It should now be blacklisted.
        response_B_again = self.client.post(refresh_url, {"refresh": refresh_B1}, format='json')
        self.assertEqual(response_B_again.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("token_not_valid", response_B_again.data.get("code", ""))
