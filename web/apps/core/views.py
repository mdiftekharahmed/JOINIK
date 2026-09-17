from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.devices.models import Device
from apps.alarms.models import Alarm
from apps.core.tb_reader import get_device_online, get_last_activity
from apps.devices.sync import sync_devices_from_thingsboard


def dashboard(request):
    # Sync devices (adds new, renames, removes deleted)
    sync_devices_from_thingsboard()

    devices = Device.objects.all()

    device_statuses = []
    total_online = 0
    total_high_risk = 0

    for d in devices:
        online = get_device_online(str(d.tb_device_id))
        last_seen = get_last_activity(str(d.tb_device_id))
        if online:
            total_online += 1
        risk = d.current_risk_level or 'NORMAL'
        if risk in ('HIGH', 'CRITICAL'):
            total_high_risk += 1
        device_statuses.append({
            'device': d,
            'online': online,
            'last_seen': last_seen,
            'risk': risk,
        })

    active_alarms = Alarm.objects.filter(status__in=['ACTIVE', 'ACKNOWLEDGED']).select_related('device').order_by('-triggered_at')
    recent_events = Alarm.objects.select_related('device').order_by('-triggered_at')[:10]

    from apps.core.weather import get_current_weather
    
    context = {
        'total_devices': devices.count(),
        'total_online': total_online,
        'total_offline': devices.count() - total_online,
        'total_high_risk': total_high_risk,
        'active_alarms_count': active_alarms.count(),
        'device_statuses': device_statuses,
        'recent_events': recent_events,
        'weather_data': get_current_weather(),
        'page': 'dashboard',
    }
    return render(request, 'dashboard.html', context)

from django.http import JsonResponse

def dashboard_api(request):
    """JSON endpoint for 1-second AJAX polling on the dashboard."""
    devices = Device.objects.all()
    device_statuses = []
    total_online = 0
    total_high_risk = 0

    for d in devices:
        online = get_device_online(str(d.tb_device_id))
        last_seen = get_last_activity(str(d.tb_device_id))
        if online:
            total_online += 1
        risk = d.current_risk_level or 'NORMAL'
        if risk in ('HIGH', 'CRITICAL'):
            total_high_risk += 1
            
        # Format the date
        if last_seen:
            last_seen_str = last_seen.strftime('%Y-%m-%d %H:%M:%S UTC')
        else:
            last_seen_str = "Never"
            
        device_statuses.append({
            'tb_device_id': str(d.tb_device_id),
            'name': d.name,
            'online': online,
            'last_seen': last_seen_str,
            'risk': risk,
            'risk_lower': risk.lower(),
        })

    return JsonResponse({
        'total_devices': devices.count(),
        'total_online': total_online,
        'total_offline': devices.count() - total_online,
        'total_high_risk': total_high_risk,
        'devices': device_statuses,
    })
