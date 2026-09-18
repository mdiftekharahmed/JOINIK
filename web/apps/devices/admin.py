from django.contrib import admin
from .models import Device

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'tb_device_id', 'organization', 'weather_location', 'latitude', 'longitude', 'current_risk_level', 'added_at')
    search_fields = ('name', 'mac_address', 'tb_device_id', 'weather_location', 'latitude', 'longitude')
    list_filter = ('current_risk_level', 'organization')
