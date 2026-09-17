from django.db import models
from apps.devices.models import Device
import uuid

class AIModelVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version_tag = models.CharField(max_length=50, unique=True)
    model_file = models.FileField(upload_to='ai_models/', blank=True, null=True)
    training_samples = models.IntegerField(default=0)
    feature_list = models.JSONField(default=list)
    trained_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.version_tag

class RiskAssessment(models.Model):
    RISK_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='assessments')
    ts = models.DateTimeField()
    risk_score = models.FloatField()
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS)
    confidence = models.FloatField()
    alarm_triggered = models.BooleanField(default=False)
    alarm_reason = models.TextField(blank=True, help_text="AI-Generated reason for the alarm")
    feature_snapshot = models.JSONField(default=dict)
    shap_values = models.JSONField(default=dict, blank=True, null=True)
    model_version = models.ForeignKey(AIModelVersion, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.device.name} - {self.risk_score} at {self.ts}"
