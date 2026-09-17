from django.contrib import admin
from .models import Alarm, HumanVerification

@admin.register(Alarm)
class AlarmAdmin(admin.ModelAdmin):
    pass

@admin.register(HumanVerification)
class HumanVerificationAdmin(admin.ModelAdmin):
    pass

