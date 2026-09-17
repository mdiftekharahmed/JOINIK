from django.db import models
from django.contrib.auth.models import User
import uuid

class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    ROLES = [
        ('SYSTEM_ADMIN', 'System Admin'),
        ('ORG_ADMIN', 'Organization Admin'),
        ('OPERATOR', 'Operator'),
        ('VIEWER', 'Viewer'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLES, default='VIEWER')

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"
