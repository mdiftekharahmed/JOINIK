from django.db import models
from django.contrib.auth.models import User
from apps.devices.models import Device
from apps.ai_engine.models import RiskAssessment
import uuid

class Alarm(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Cancellation (10s)'),
        ('CANCELLED', 'Cancelled'),
        ('ESCALATING', 'Escalating'),
        ('EMERGENCY_NOTIFIED', 'Emergency Notified'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Resolved'),
        ('FALSE_ALARM', 'False Alarm'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='alarms')
    tb_alarm_id = models.UUIDField(null=True, blank=True)
    risk_level = models.CharField(max_length=10, choices=RiskAssessment.RISK_LEVELS)
    risk_score = models.FloatField()
    ai_confidence = models.FloatField(default=0.0)
    triggered_at = models.DateTimeField(auto_now_add=True)
    
    # Escalation fields
    cancellation_deadline = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_alarms')
    
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_alarms')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alarms')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True)
    triggering_keys = models.JSONField(default=list)
    assessment = models.ForeignKey(RiskAssessment, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.risk_level} on {self.device.name} at {self.triggered_at}"

class HumanVerification(models.Model):
    VERDICTS = [
        ('CONFIRMED', 'Confirmed Intrusion'),
        ('FALSE_ALARM', 'False Alarm'),
        ('MAINTENANCE', 'Maintenance'),
        ('UNKNOWN', 'Unknown'),
    ]

    alarm = models.OneToOneField(Alarm, on_delete=models.CASCADE, related_name='verification')
    verdict = models.CharField(max_length=20, choices=VERDICTS)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
