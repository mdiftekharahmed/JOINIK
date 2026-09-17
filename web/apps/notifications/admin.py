from django.contrib import admin
from .models import NotificationRule, EmergencyContact, NotificationLog

@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    pass

@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'channel', 'target_address', 'priority', 'is_active', 'is_verified')
    list_filter = ('channel', 'is_active', 'is_verified')
    search_fields = ('name', 'target_address')

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('alarm', 'contact', 'status', 'sent_at')
    list_filter = ('status',)
