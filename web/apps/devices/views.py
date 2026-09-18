from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Device
from .forms import DeviceForm
from .sync import sync_devices_from_thingsboard
from apps.core.tb_api import ThingsBoardAPI
from apps.core.tb_reader import get_latest_telemetry, get_device_online, get_last_activity

def device_list(request):
    # Full bi-directional sync: adds new, renames updated, deletes removed
    sync_result = sync_devices_from_thingsboard()
    if sync_result['added']:
        messages.info(request, f"{sync_result['added']} new device(s) synced from ThingsBoard.")
    if sync_result['deleted']:
        messages.warning(
            request,
            f"{sync_result['deleted']} device(s) were removed because they no longer exist in ThingsBoard."
        )


    devices = Device.objects.all()
    device_data = []
    
    for d in devices:
        online = get_device_online(str(d.tb_device_id))
        last_seen = get_last_activity(str(d.tb_device_id))
        device_data.append({
            'obj': d,
            'online': online,
            'last_seen': last_seen,
        })
        
    if request.method == 'POST':
        form = DeviceForm(request.POST)
        if form.is_valid():
            device_inst = form.save(commit=False)
            tb_api = ThingsBoardAPI()
            try:
                # 1. Create in ThingsBoard
                tb_resp = tb_api.create_device(device_inst.name)
                tb_device_id = tb_resp.get('id', {}).get('id')
                
                # 2. Get Credentials
                creds_resp = tb_api.get_device_credentials(tb_device_id)
                access_token = creds_resp.get('credentialsId')
                
                # 3. Save to Django DB
                device_inst.tb_device_id = tb_device_id
                device_inst.tb_access_token = access_token
                device_inst.save()
                
                messages.success(request, f"Device '{device_inst.name}' added successfully! Access token: {access_token}")
                return redirect('device_list')
            except Exception as e:
                messages.error(request, f"Failed to provision device in ThingsBoard: {e}")
    else:
        form = DeviceForm()
        
    context = {
        'devices': device_data,
        'form': form,
    }
    return render(request, 'devices/list.html', context)

def device_detail(request, device_id):
    device = get_object_or_404(Device, tb_device_id=device_id)
    latest = get_latest_telemetry(str(device.tb_device_id))
    online = get_device_online(str(device.tb_device_id))
    last_seen = get_last_activity(str(device.tb_device_id))
    
    alarms = device.alarms.all().order_by('-triggered_at')[:5]
    
    from apps.core.weather import get_current_weather
    weather_data = get_current_weather(device.weather_location)
    
    # ── Auto-populate MAC from ThingsBoard live telemetry ─────────────────────
    live_mac = None
    if 'device_mac' in latest:
        live_mac = latest['device_mac'].get('value', '')
    if live_mac and device.mac_address != live_mac:
        Device.objects.filter(pk=device.pk).update(mac_address=live_mac)
        device.mac_address = live_mac
    
    # ── Latest AI analysis result from analysis_db ────────────────────────────
    latest_analysis = None
    try:
        from apps.ai_engine.models import AnalysisResult
        latest_analysis = AnalysisResult.objects.using('analysis_db').filter(device_id=device.id).order_by('-ts').first()
    except Exception:
        pass  # analysis_db may not be migrated yet

    # ── Build a unified AI snapshot (analysis_db > device model > zeros) ──────
    if latest_analysis:
        ai_snapshot = {
            'alarm':      latest_analysis.alarm,
            'risk_level': latest_analysis.risk_level,
            'risk_score': latest_analysis.risk_score,
            'confidence': round(latest_analysis.confidence * 100, 1) if latest_analysis.confidence <= 1.0 else round(latest_analysis.confidence, 1),
            'reason':     latest_analysis.alarm_reason or 'All parameters within normal range',
        }
    else:
        # Fallback to device model fields written by tasks.py
        ai_snapshot = {
            'alarm':      False,
            'risk_level': device.current_risk_level or 'NORMAL',
            'risk_score': device.current_risk_score or 0.0,
            'confidence': 95.0,
            'reason':     'No analysis data yet',
        }
    
    context = {
        'device': device,
        'latest': latest,
        'online': online,
        'last_seen': last_seen,
        'alarms': alarms,
        'weather_data': weather_data,
        'latest_analysis': latest_analysis,
        'ai_snapshot': ai_snapshot,
    }
    return render(request, 'devices/detail.html', context)
