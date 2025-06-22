from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import decimal
import uuid # For WalletDepositRequest ID
from channels.layers import get_channel_layer # For WebSocket updates
from asgiref.sync import async_to_sync       # For WebSocket updates
import json                                   # For WebSocket updates

class UserWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(
        max_digits=19,
        decimal_places=8,
        default=decimal.Decimal('0.0'),
        validators=[MinValueValidator(decimal.Decimal('0.0'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Wallet"
        verbose_name_plural = "User Wallets"

    def __str__(self):
        return f"{self.user.username}'s Wallet - Balance: {self.balance}"

    def add_credit(self, amount_to_add, description=""):
        if not isinstance(amount_to_add, decimal.Decimal):
            amount_to_add = decimal.Decimal(str(amount_to_add))
        if amount_to_add <= decimal.Decimal('0.0'):
            raise ValueError("Credit amount must be positive.")

        with transaction.atomic():
            self.balance += amount_to_add
            self.save(update_fields=['balance', 'updated_at'])
            WalletTransaction.objects.create(
                wallet=self,
                transaction_type='credit',
                amount=amount_to_add,
                description=description
            )
            # Send WebSocket update
            channel_layer = get_channel_layer()
            group_name = f"user_{self.user.id}_wallet"
            message_payload = {
                'type': 'send_wallet_update', # Matches consumer method
                'message': {
                    'user_id': self.user.id,
                    'balance': str(self.balance), # Ensure Decimal is serialized as string
                    'last_updated': self.updated_at.isoformat(),
                    'description': description,
                    'transaction_type': 'credit',
                    'transaction_amount': str(amount_to_add)
                }
            }
            if channel_layer is not None:
                async_to_sync(channel_layer.group_send)(group_name, message_payload)
        return self.balance

    def deduct_credit(self, amount_to_deduct, description=""):
        if not isinstance(amount_to_deduct, decimal.Decimal):
            amount_to_deduct = decimal.Decimal(str(amount_to_deduct))
        if amount_to_deduct <= decimal.Decimal('0.0'):
            raise ValueError("Deduction amount must be positive.")

        with transaction.atomic():
            if self.balance < amount_to_deduct:
                raise ValueError("Insufficient balance for deduction.")
            self.balance -= amount_to_deduct
            self.save(update_fields=['balance', 'updated_at'])
            WalletTransaction.objects.create(
                wallet=self,
                transaction_type='debit',
                amount=amount_to_deduct,
                description=description
            )
            # Send WebSocket update
            channel_layer = get_channel_layer()
            group_name = f"user_{self.user.id}_wallet"
            message_payload = {
                'type': 'send_wallet_update', # Matches consumer method
                'message': {
                    'user_id': self.user.id,
                    'balance': str(self.balance), # Ensure Decimal is serialized as string
                    'last_updated': self.updated_at.isoformat(),
                    'description': description,
                    'transaction_type': 'debit',
                    'transaction_amount': str(amount_to_deduct)
                }
            }
            if channel_layer is not None:
                async_to_sync(channel_layer.group_send)(group_name, message_payload)
        return self.balance

class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
        ('reversal', 'Reversal'), # For corrections
        ('initial', 'Initial Balance'), # For initial setup if any
    ]
    wallet = models.ForeignKey(UserWallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=19, decimal_places=8)
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    # Potentially link to an admin user who performed an action, or a related trade ID
    # admin_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='admin_wallet_actions')
    # trade_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)


    class Meta:
        verbose_name = "Wallet Transaction"
        verbose_name_plural = "Wallet Transactions"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.wallet.user.username} - {self.get_transaction_type_display()} {self.amount} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# Signals for UserWallet creation (from previous step, ensure they are still there)
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        UserWallet.objects.create(user=instance)

# save_user_wallet signal might be redundant if wallet is always created with user.
# @receiver(post_save, sender=User)
# def save_user_wallet(sender, instance, **kwargs):
#     try:
#         instance.wallet.save()
#     except UserWallet.DoesNotExist:
#         UserWallet.objects.create(user=instance)

class WalletDepositRequest(models.Model):
    DEPOSIT_STATUS_CHOICES = [
        ('pending_user_action', 'Pending User Action'), # User needs to make the transfer
        ('pending_confirmation', 'Pending Admin Confirmation'), # User claims transfer made, admin to verify
        ('completed', 'Completed'), # Admin confirmed, wallet credited
        ('failed', 'Failed'),     # e.g., user cancelled, or issue found
        ('expired', 'Expired'),   # If not acted upon in time
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposit_requests')
    amount_requested = models.DecimalField(max_digits=19, decimal_places=8, help_text="Amount user intends to deposit in USDT")
    currency = models.CharField(max_length=10, default="USDT") # For now, only USDT
    status = models.CharField(max_length=30, choices=DEPOSIT_STATUS_CHOICES, default='pending_user_action')

    # Optional: fields for admin to record transaction details they found
    blockchain_tx_id = models.CharField(max_length=255, blank=True, null=True, help_text="Blockchain Transaction ID provided by user or found by admin")
    admin_notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wallet Deposit Request"
        verbose_name_plural = "Wallet Deposit Requests"
        ordering = ['-created_at']

    def __str__(self):
        return f"Deposit request {self.id} by {self.user.username} for {self.amount_requested} {self.currency} - Status: {self.get_status_display()}"
