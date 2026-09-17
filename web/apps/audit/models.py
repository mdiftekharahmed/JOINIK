from django.db import models
from django.contrib.auth.models import User
import uuid

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100)
    detail = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.action} on {self.target_type} at {self.timestamp}"
