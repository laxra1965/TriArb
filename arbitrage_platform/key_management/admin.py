from django.contrib import admin
from .models import UserAPIKey

@admin.register(UserAPIKey)
class UserAPIKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'exchange_name', 'api_key', 'updated_at')
    list_filter = ('exchange_name', 'user__username')
    search_fields = ('api_key', 'user__username', 'exchange_name')
    # readonly_fields = ('_api_secret_encrypted',) # This was duplicated, corrected below

    # To allow setting secret via admin (uses property with encryption)
    # Note: For production, direct editing of secrets in admin might be undesirable.
    # A custom form or action might be better.
    fieldsets = (
        (None, {
            'fields': ('user', 'exchange_name', 'api_key', 'api_secret', '_api_secret_encrypted')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',) # Keep timestamps collapsed by default
        }),
    )
    # Make created_at, updated_at and _api_secret_encrypted readonly
    readonly_fields = ('created_at', 'updated_at', '_api_secret_encrypted')
