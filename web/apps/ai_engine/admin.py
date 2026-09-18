from django.contrib import admin
from .models import RiskAssessment, AIModelVersion, AnalysisResult

@admin.register(AIModelVersion)
class AIModelVersionAdmin(admin.ModelAdmin):
    list_display = ('version_tag', 'is_active', 'trained_at', 'training_samples')
    list_filter = ('is_active',)
    search_fields = ('version_tag',)

@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ('device', 'risk_score', 'risk_level', 'alarm_triggered', 'ts')
    list_filter = ('risk_level', 'alarm_triggered')
    search_fields = ('device__name',)

@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ('device', 'event_type', 'risk_level', 'alarm', 'persistence_ratio', 'ts')
    list_filter = ('risk_level', 'event_type', 'alarm')
    search_fields = ('device__name',)
    readonly_fields = ('ts', 'created_at')
