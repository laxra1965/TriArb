from django.db import models
from django.contrib.auth.models import User
# from key_management.models import UserAPIKey # If linking directly to the key used
# from wallet_management.models import UserWallet # If linking to wallet
import decimal
import uuid # For a unique trade attempt ID linking legs

class ArbitrageTradeAttempt(models.Model):
    """ Represents a single attempt to execute a full triangular arbitrage. Links multiple TradeOrderLegs. """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_attempts')
    # Opportunity details can be stored as JSON or broken down if needed for querying often
    opportunity_details_json = models.JSONField(help_text="Snapshot of the arbitrage opportunity data at time of attempt")
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partially_completed', 'Partially Completed'), # If some legs succeed but not all
    ])
    # Optional: Link to a main UserAPIKey if one exchange is primary, or handle per leg
    # user_api_key = models.ForeignKey(UserAPIKey, null=True, blank=True, on_delete=models.SET_NULL)
    start_amount_base_coin = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True)
    final_amount_base_coin = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True) # Actual outcome
    calculated_profit = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True) # Expected profit
    actual_profit = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True)
    commission_deducted = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True)
    admin_notes = models.TextField(blank=True, null=True, help_text="Internal notes for admin, e.g., about commission issues.")
    error_message = models.TextField(blank=True, null=True, help_text="Error message if the overall attempt failed.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Attempt {self.id} by {self.user.username} - {self.status}"

    class Meta:
        ordering = ['-created_at']


class TradeOrderLeg(models.Model):
    """ Represents a single leg of an arbitrage trade attempt. """
    ORDER_SIDE_CHOICES = [('BUY', 'Buy'), ('SELL', 'Sell')]
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),            # Not yet sent to exchange
        ('new', 'New'),                    # Sent to exchange, acknowledged
        ('partially_filled', 'Partially Filled'),
        ('filled', 'Filled'),
        ('canceled', 'Canceled'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('error', 'Error'),                # Error during placement or processing
    ]

    attempt = models.ForeignKey(ArbitrageTradeAttempt, on_delete=models.CASCADE, related_name='legs')
    leg_number = models.PositiveSmallIntegerField(help_text="Sequence number of this leg (1, 2, or 3)")

    exchange_name = models.CharField(max_length=50)
    # user_api_key = models.ForeignKey(UserAPIKey, on_delete=models.SET_NULL, null=True, blank=True) # Key used for this leg

    pair = models.CharField(max_length=30) # e.g., BTC/USDT
    side = models.CharField(max_length=4, choices=ORDER_SIDE_CHOICES)

    # Amounts and Prices
    # Intended/calculated amounts before execution
    intended_quantity = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True)
    intended_price = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True, help_text="Estimated price at calculation")

    # Actual amounts and prices after execution (if available)
    executed_quantity = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True)
    executed_price_avg = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True, help_text="Average fill price")

    # Exchange specific details
    exchange_order_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, default='pending', choices=ORDER_STATUS_CHOICES)

    # Fees
    fee_amount = models.DecimalField(max_digits=19, decimal_places=8, null=True, blank=True)
    fee_currency = models.CharField(max_length=20, null=True, blank=True)

    error_message = models.TextField(blank=True, null=True, help_text="Error message if the order leg failed")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('attempt', 'leg_number') # Each leg in an attempt is unique
        ordering = ['attempt', 'leg_number']

    def __str__(self):
        return f"Leg {self.leg_number} ({self.side} {self.pair} on {self.exchange_name}) for Attempt {self.attempt_id}"
