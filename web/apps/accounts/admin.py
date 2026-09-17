from django.contrib import admin
from .models import Organization, UserProfile

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    pass

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    pass

