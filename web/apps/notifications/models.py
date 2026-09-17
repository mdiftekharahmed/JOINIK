from django.db import models
from django.contrib.auth.models import User
from apps.alarms.models import Alarm
import uuid

class NotificationRule(models.Model):
    CHANNELS = [
        ('EMAIL', 'Email'),
        ('TELEGRAM', 'Telegram'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_rules')
    channel = models.CharField(max_length=20, choices=CHANNELS)
    target_address = models.CharField(max_length=255)
    min_risk_level = models.CharField(max_length=10, choices=[
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ], default='HIGH')
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user} - {self.channel} for {self.min_risk_level}+"

class EmergencyContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    organization = models.CharField(max_length=150, blank=True)
    channel = models.CharField(max_length=20, choices=NotificationRule.CHANNELS)
    target_address = models.CharField(max_length=255)
    priority = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} ({self.channel}) - Priority {self.priority}"

class NotificationLog(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('ACKNOWLEDGED', 'Acknowledged'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alarm = models.ForeignKey(Alarm, on_delete=models.CASCADE, related_name='notifications')
    contact = models.ForeignKey(EmergencyContact, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    def __str__(self):
        return f"To {self.contact.name} for Alarm {self.alarm.id} - {self.status}"

