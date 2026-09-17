from django.contrib import admin
from .models import SystemSettings

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # if there's already an entry, do not allow adding
        count = SystemSettings.objects.all().count()
        if count == 0:
            return True
        return False
