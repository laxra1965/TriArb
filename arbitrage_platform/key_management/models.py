from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
import base64

# Initialize Fernet with a key derived from settings.SECRET_KEY
# IMPORTANT: For production, use a dedicated, securely managed key,
# preferably loaded from an environment variable and not hardcoded or derived
# from a key used for other purposes like Django's SECRET_KEY.
# For this example, we'll ensure the key is URL-safe base64 encoded and 32 bytes.
# A simple approach is to hash SECRET_KEY to get a consistent 32-byte key.
import hashlib
fernet_key_base = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
# Fernet keys must be base64 encoded.
FERNET_KEY = base64.urlsafe_b64encode(fernet_key_base[:32]) # Use first 32 bytes of hash
cipher_suite = Fernet(FERNET_KEY)

def encrypt_secret(secret_text):
    if not secret_text:
        return None # Store as NULL if empty
    # Ensure secret_text is bytes
    secret_bytes = secret_text.encode('utf-8')
    encrypted_bytes = cipher_suite.encrypt(secret_bytes)
    # Store as base64 encoded string to be safe for TextField
    return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')

def decrypt_secret(encrypted_text):
    if not encrypted_text:
        return ''
    try:
        # Decode from base64 string storage
        encrypted_bytes_from_storage = base64.urlsafe_b64decode(encrypted_text.encode('utf-8'))
        decrypted_bytes = cipher_suite.decrypt(encrypted_bytes_from_storage)
        return decrypted_bytes.decode('utf-8')
    except InvalidToken:
        # Handle cases where decryption fails (e.g., malformed token, wrong key)
        # Log this error in a real application
        return '' # Or raise an exception
    except Exception as e:
        # Handle other potential errors during decryption
        # Log this error
        return '' # Or raise an exception


class UserAPIKey(models.Model):
    EXCHANGE_CHOICES = [
        ('Binance', 'Binance'),
        ('Bybit', 'Bybit'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    exchange_name = models.CharField(max_length=50, choices=EXCHANGE_CHOICES)
    api_key = models.CharField(max_length=255, unique=True)
    # Changed to TextField to store base64 encoded encrypted bytes
    _api_secret_encrypted = models.TextField(blank=True, null=True, help_text="Encrypted API secret (Fernet)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_api_secret(self, secret_text):
        self._api_secret_encrypted = encrypt_secret(secret_text)

    def get_api_secret(self):
        return decrypt_secret(self._api_secret_encrypted)

    api_secret = property(get_api_secret, set_api_secret)

    class Meta:
        unique_together = ('user', 'exchange_name')
        verbose_name = "User API Key"
        verbose_name_plural = "User API Keys"

    def __str__(self):
        return f"{self.user.username}'s {self.exchange_name} Key"
