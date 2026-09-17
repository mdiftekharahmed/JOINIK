from apps.alarms.models import Alarm

def global_alarm_counts(request):
    """
    Injects count of active PENDING, ESCALATING, and EMERGENCY_NOTIFIED alarms
    globally so the sidebar can show notification badges.
    """
    if request.user.is_authenticated:
        # Get count of alarms that are NOT resolved or cancelled
        active_alarms = Alarm.objects.filter(status__in=['PENDING', 'ESCALATING', 'EMERGENCY_NOTIFIED'])
        
        critical_count = active_alarms.filter(risk_level='CRITICAL').count()
        high_count = active_alarms.filter(risk_level='HIGH').count()
        total_active = active_alarms.count()
        
        return {
            'nav_alarms_critical': critical_count,
            'nav_alarms_high': high_count,
            'nav_alarms_total': total_active
        }
    return {}

def joinik_context(request):
    """
    Global context processor.
    """
    return {}
