from django.db import models
from apps.accounts.models import Organization
import uuid


class Device(models.Model):
    RISK_LEVELS = [
        ('NORMAL', 'Normal'),
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tb_device_id = models.UUIDField(unique=True, help_text="ThingsBoard device UUID")
    name = models.CharField(max_length=120)
    mac_address = models.CharField(max_length=17, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='devices')
    location_name = models.CharField(max_length=200, blank=True)
    location_x = models.FloatField(default=0.5, help_text="0.0–1.0 for SVG floorplan")
    location_y = models.FloatField(default=0.5)
    latitude = models.FloatField(default=23.8103, help_text="Latitude for weather API (default Dhaka)")
    longitude = models.FloatField(default=90.4125, help_text="Longitude for weather API (default Dhaka)")
    weather_location = models.CharField(max_length=100, blank=True, null=True, help_text="City name for the weather widget")
    firmware_version = models.CharField(max_length=50, blank=True)
    tb_access_token = models.CharField(max_length=255, blank=True,
                                       help_text="ThingsBoard device access token")
    current_risk_level = models.CharField(max_length=10, choices=RISK_LEVELS,
                                          default='NORMAL')
    current_risk_score = models.FloatField(default=0.0)
    added_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def risk_badge_class(self):
        return {
            'NORMAL': 'badge-normal',
            'LOW': 'badge-low',
            'MEDIUM': 'badge-medium',
            'HIGH': 'badge-high',
            'CRITICAL': 'badge-critical',
        }.get(self.current_risk_level, 'badge-normal')
