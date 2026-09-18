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
    
    # We will get alarms and assessments later, keep it simple for now
    alarms = device.alarms.all().order_by('-triggered_at')[:5]
    
    from apps.core.weather import get_current_weather
    weather_data = get_current_weather(device.weather_location)
    
    from apps.ai_engine.models import AnalysisResult
    latest_analysis = AnalysisResult.objects.using('analysis_db').filter(device=device).order_by('-ts').first()
    
    context = {
        'device': device,
        'latest': latest,
        'online': online,
        'last_seen': last_seen,
        'alarms': alarms,
        'weather_data': weather_data,
        'latest_analysis': latest_analysis,
    }
    return render(request, 'devices/detail.html', context)
