from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Alarm
import logging

logger = logging.getLogger(__name__)

# @login_required
def alarm_list(request):
    status_filter = request.GET.get('status', 'ACTIVE')
    
    if status_filter == 'ALL':
        alarms = Alarm.objects.select_related('device').order_by('-triggered_at')
    else:
        alarms = Alarm.objects.select_related('device').filter(status=status_filter).order_by('-triggered_at')
        
    context = {
        'alarms': alarms,
        'status_filter': status_filter,
        'page': 'alarms',
    }
    return render(request, 'alarms/list.html', context)

def alarm_detail(request, alarm_id):
    alarm = get_object_or_404(Alarm, id=alarm_id)
    notifications = alarm.notifications.all().order_by('-sent_at')
    
    # Sensor Correlation: Fetch telemetry 5 seconds before and 5 seconds after trigger
    from apps.core.tb_reader import get_telemetry_range
    import time
    
    trigger_ts_ms = int(alarm.triggered_at.timestamp() * 1000)
    start_ts = trigger_ts_ms - 5000
    end_ts = trigger_ts_ms + 5000
    
    # We only care about keys that could trigger an event
    relevant_keys = ['motion', 'accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z', 'cctv_cut', 'powercut']
    
    raw_telemetry = get_telemetry_range(str(alarm.device.tb_device_id), start_ts, end_ts, keys=relevant_keys)
    
    # Identify significant events for the correlation timeline
    correlation_events = []
    
    # Add the alarm trigger as the central event
    correlation_events.append({
        'ts_ms': trigger_ts_ms,
        'label': 'AI EVALUATION: HIGH RISK',
        'type': 'ai_eval',
        'offset_ms': 0
    })
    
    # Process raw telemetry to find spikes or boolean triggers
    for row in raw_telemetry:
        key = row['key']
        val = row['value']
        ts = row['ts_ms']
        
        offset = ts - trigger_ts_ms
        
        is_event = False
        label = ""
        
        if key in ['motion', 'cctv_cut', 'powercut'] and val == 1:
            is_event = True
            label = f"{key.upper()} DETECTED"
        elif key.startswith('accel_') and abs(val) > 4.0:
            is_event = True
            label = f"ACCELERATION SPIKE ({val:.1f}g)"
        elif key.startswith('gyro_') and abs(val) > 150.0:
            is_event = True
            label = f"GYROSCOPE SPIKE ({val:.1f}°/s)"
            
        if is_event:
            correlation_events.append({
                'ts_ms': ts,
                'label': label,
                'type': 'sensor',
                'offset_ms': offset
            })
            
    # Sort events chronologically
    correlation_events.sort(key=lambda x: x['ts_ms'])
    
    context = {
        'alarm': alarm,
        'notifications': notifications,
        'correlation_events': correlation_events,
        'page': 'alarms'
    }
    return render(request, 'alarms/investigation.html', context)

# @login_required
def alarm_action(request, alarm_id):
    if request.method == 'POST':
        alarm = get_object_or_404(Alarm, id=alarm_id)
        action = request.POST.get('action')
        notes = request.POST.get('notes', '').strip()
        
        user = request.user if request.user.is_authenticated else None
        
        if action == 'acknowledge':
            alarm.status = 'ACKNOWLEDGED'
            alarm.acknowledged_at = timezone.now()
            alarm.acknowledged_by = user
        elif action == 'resolve':
            alarm.status = 'RESOLVED'
            alarm.resolved_at = timezone.now()
            alarm.resolved_by = user
        elif action == 'false_alarm':
            alarm.status = 'FALSE_ALARM'
            alarm.resolved_at = timezone.now()
            alarm.resolved_by = user
            
        if notes:
            alarm.notes = f"{alarm.notes}\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] {action.upper()}: {notes}".strip()
            
        alarm.save()
        logger.info(f"Alarm {alarm_id} status updated to {alarm.status} by {user}")
        
    # Redirect back to where they came from (or fallback to alarms list)
    return redirect(request.META.get('HTTP_REFERER', 'alarm_list'))

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# @csrf_exempt if needed for local testing, but better to keep CSRF
def cancel_alarm_api(request, alarm_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            pin = data.get('pin')
            reason = data.get('reason')
            
            # Simple mock PIN validation for the demo
            if pin != '1234':
                return JsonResponse({'success': False, 'error': 'Invalid PIN'})
                
            alarm = get_object_or_404(Alarm, id=alarm_id)
            
            # Only allow cancelling PENDING alarms
            if alarm.status != 'PENDING':
                return JsonResponse({'success': False, 'error': f'Alarm is already {alarm.status}'})
                
            # Cancel the alarm
            alarm.status = 'CANCELLED'
            alarm.cancellation_reason = reason
            alarm.cancelled_by = request.user if request.user.is_authenticated else None
            alarm.save()
            
            logger.info(f"Alarm {alarm_id} CANCELLED by {alarm.cancelled_by} with reason: {reason}")
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid method'})
