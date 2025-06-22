from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from .models import UserWallet, WalletTransaction, WalletDepositRequest # Add WalletDepositRequest
from django import forms
from decimal import Decimal
from django.utils import timezone # Added for admin actions

class WalletTransactionInline(admin.TabularInline):
    model = WalletTransaction
    extra = 0
    readonly_fields = ('timestamp', 'transaction_type', 'amount', 'description')
    can_delete = False
    ordering = ('-timestamp',)
    # Do not allow adding transactions directly here, use actions or specific views.

class UserWalletAdminForm(forms.ModelForm):
    # Field for admin to input amount for manual adjustment
    adjustment_amount = forms.DecimalField(required=False, max_digits=19, decimal_places=8)
    adjustment_description = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = UserWallet
        fields = '__all__'


@admin.register(UserWallet)
class UserWalletAdmin(admin.ModelAdmin):
    form = UserWalletAdminForm
    list_display = ('user_link', 'balance', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'balance') # Balance made readonly to force use of actions
    inlines = [WalletTransactionInline]

    fieldsets = (
        (None, {'fields': ('user', 'balance', ('created_at', 'updated_at'))}),
        ('Manual Adjustment (Admin Only)', {'fields': ('adjustment_amount', 'adjustment_description')}),
    )

    def user_link(self, obj):
        # Link to the user's change page in admin
        user_admin_url = reverse('admin:auth_user_change', args=(obj.user.pk,))
        return format_html('<a href="{}">{}</a>', user_admin_url, obj.user.username)
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user'


    def save_model(self, request, obj, form, change):
        # obj is the UserWallet instance
        # form.cleaned_data contains all form fields including custom ones
        super().save_model(request, obj, form, change) # Save UserWallet first if other fields changed

        adjustment_amount = form.cleaned_data.get('adjustment_amount')
        adjustment_description = form.cleaned_data.get('adjustment_description', 'Admin adjustment')

        if adjustment_amount and adjustment_amount != Decimal('0.0'):
            try:
                if adjustment_amount > Decimal('0.0'):
                    obj.add_credit(adjustment_amount, description=f"Admin Credit: {adjustment_description}")
                    self.message_user(request, f"Successfully credited {adjustment_amount} to {obj.user.username}.", messages.SUCCESS)
                else: # Negative adjustment_amount means debit
                    obj.deduct_credit(abs(adjustment_amount), description=f"Admin Debit: {adjustment_description}")
                    self.message_user(request, f"Successfully debited {abs(adjustment_amount)} from {obj.user.username}.", messages.SUCCESS)
            except ValueError as e:
                self.message_user(request, f"Error adjusting balance for {obj.user.username}: {str(e)}", messages.ERROR)
        # Note: adjustment_amount and description are not part of the UserWallet model,
        # so they don't need to be cleared from the instance. They are form-only fields.

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet_user', 'transaction_type', 'amount', 'timestamp', 'description_snippet')
    list_filter = ('transaction_type', 'timestamp', 'wallet__user__username')
    search_fields = ('wallet__user__username', 'description')
    readonly_fields = ('wallet', 'transaction_type', 'amount', 'timestamp', 'description') # Generally non-editable

    def wallet_user(self, obj):
        return obj.wallet.user.username
    wallet_user.short_description = 'User'
    wallet_user.admin_order_field = 'wallet__user'

    def description_snippet(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else obj.description
    description_snippet.short_description = 'Description'

    def has_add_permission(self, request): # Prevent manual creation of transactions
        return False
    def has_change_permission(self, request, obj=None): # Prevent manual changes
        return False
    # Allow deletion by admin if necessary, but typically transactions are immutable.
    # def has_delete_permission(self, request, obj=None):
    # return True


@admin.register(WalletDepositRequest)
class WalletDepositRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_link', 'amount_requested', 'currency', 'status_display_colored', 'created_at', 'blockchain_tx_id')
    list_filter = ('status', 'currency', 'created_at', 'user__username')
    search_fields = ('id', 'user__username', 'blockchain_tx_id')
    readonly_fields = ('id', 'user', 'amount_requested', 'currency', 'created_at', 'updated_at') # Most fields are readonly for admin action
    ordering = ('-created_at',)

    fieldsets = (
        ("Request Details", {'fields': ('id', 'user', 'amount_requested', 'currency', 'status', 'blockchain_tx_id', 'created_at', 'updated_at')}),
        ("Admin Action", {'fields': ('admin_notes',)}), # Admin can add notes
    )

    actions = ['mark_as_completed_and_credit_wallet', 'mark_as_failed']

    def user_link(self, obj):
        user_admin_url = reverse('admin:auth_user_change', args=(obj.user.pk,))
        return format_html('<a href="{}">{}</a>', user_admin_url, obj.user.username)
    user_link.short_description = 'User'
    # user_link.admin_order_field = 'user' # Already defined in UserWalletAdmin, ensure no conflict if used in same list display

    def status_display_colored(self, obj):
        status_colors = {
            'pending_user_action': 'orange',
            'pending_confirmation': 'blue',
            'completed': 'green',
            'failed': 'red',
            'expired': 'grey',
        }
        color = status_colors.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())
    status_display_colored.short_description = 'Status'
    status_display_colored.admin_order_field = 'status'


    def mark_as_completed_and_credit_wallet(self, request, queryset):
        for deposit_request in queryset.filter(status='pending_confirmation'):
            try:
                wallet = deposit_request.user.wallet
                wallet.add_credit(deposit_request.amount_requested,
                                  description=f"Deposit confirmed for request {deposit_request.id}. TxID: {deposit_request.blockchain_tx_id or 'N/A'}")
                deposit_request.status = 'completed'
                deposit_request.admin_notes = (deposit_request.admin_notes or "") + f"\nConfirmed by {request.user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}."
                deposit_request.save()
                self.message_user(request, f"Deposit request {deposit_request.id} marked as completed and wallet credited for {deposit_request.user.username}.", messages.SUCCESS)
            except UserWallet.DoesNotExist:
                self.message_user(request, f"Wallet not found for user {deposit_request.user.username} of request {deposit_request.id}.", messages.ERROR)
            except Exception as e:
                self.message_user(request, f"Error processing request {deposit_request.id}: {str(e)}", messages.ERROR)
    mark_as_completed_and_credit_wallet.short_description = "Mark selected as Completed & Credit Wallet"

    def mark_as_failed(self, request, queryset):
        for deposit_request in queryset.filter(status__in=['pending_confirmation', 'pending_user_action']):
            deposit_request.status = 'failed'
            deposit_request.admin_notes = (deposit_request.admin_notes or "") + f"\nMarked as failed by {request.user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}."
            deposit_request.save()
            self.message_user(request, f"Deposit request {deposit_request.id} marked as failed.", messages.INFO)
    mark_as_failed.short_description = "Mark selected as Failed"
