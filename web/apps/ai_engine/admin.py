from django.contrib import admin
from .models import RiskAssessment, AIModelVersion

@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    pass

@admin.register(AIModelVersion)
class AIModelVersionAdmin(admin.ModelAdmin):
    pass

