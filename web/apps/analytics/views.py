from django.shortcuts import render, get_object_or_404
from apps.devices.models import Device
from apps.core.tb_reader import get_scan_sessions, get_session_telemetry

def scan_sessions_list(request, device_id):
    device = get_object_or_404(Device, tb_device_id=device_id)
    
    page = int(request.GET.get('page', 1))
    limit = 50
    offset = (page - 1) * limit
    
    sessions = get_scan_sessions(str(device.tb_device_id), limit=limit, offset=offset)
    
    # Calculate peak metrics for each session
    # For a real large-scale app, we might want to do this via SQL,
    # but pulling the telemetry per session is okay for a few sessions on a page
    for s in sessions:
        telemetry = get_session_telemetry(str(device.tb_device_id), s['session_id'])
        max_accel = 0.0
        max_gyro = 0.0
        for r in telemetry:
            # find max accel vector magnitude
            ax, ay, az = r.get('accel_x', 0), r.get('accel_y', 0), r.get('accel_z', 0)
            a_mag = (ax**2 + ay**2 + az**2)**0.5
            if a_mag > max_accel: max_accel = a_mag
            
            gx, gy, gz = r.get('gyro_x', 0), r.get('gyro_y', 0), r.get('gyro_z', 0)
            g_mag = (gx**2 + gy**2 + gz**2)**0.5
            if g_mag > max_gyro: max_gyro = g_mag
            
        s['peak_accel'] = max_accel
        s['peak_gyro'] = max_gyro
    
    context = {
        'device': device,
        'sessions': sessions,
        'page': page,
        'has_next': len(sessions) == limit,
        'has_prev': page > 1,
        'next_page': page + 1,
        'prev_page': page - 1,
    }
    return render(request, 'analytics/sessions.html', context)
