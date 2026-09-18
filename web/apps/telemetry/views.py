import csv
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from apps.devices.models import Device
from apps.core.tb_reader import get_all_telemetry_rows, get_known_keys

def telemetry_table(request, device_id):
    device = get_object_or_404(Device, tb_device_id=device_id)
    keys = get_known_keys(str(device.tb_device_id))
    
    # Simple pagination
    page = int(request.GET.get('page', 1))
    limit = 50
    offset = (page - 1) * limit
    
    rows, total_count = get_all_telemetry_rows(str(device.tb_device_id), limit=limit, offset=offset)
    total_pages = (total_count // limit) + (1 if total_count % limit > 0 else 0)
    
    context = {
        'device': device,
        'keys': keys,
        'rows': rows,
        'page': page,
        'total_pages': total_pages,
        'total_rows': total_count,
        'has_next': page < total_pages,
        'has_prev': page > 1,
        'next_page': page + 1,
        'prev_page': page - 1,
    }
    return render(request, 'telemetry/table.html', context)


def telemetry_export_csv(request, device_id):
    device = get_object_or_404(Device, tb_device_id=device_id)
    keys = get_known_keys(str(device.tb_device_id))
    
    # Get all rows (or a large limit if too many)
    rows, _ = get_all_telemetry_rows(str(device.tb_device_id), limit=10000, offset=0)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{device.name}_telemetry.csv"'
    
    writer = csv.writer(response)
    # Header
    writer.writerow(['Timestamp'] + keys)
    
    for row in rows:
        row_data = [row['ts'].strftime('%Y-%m-%d %H:%M:%S')]
        for key in keys:
            row_data.append(row.get(key, ''))
        writer.writerow(row_data)
        
    return response

from django.http import JsonResponse
from .models import SensorParameter
import json

def parameter_list(request):
    parameters = SensorParameter.objects.all().order_by('key')
    return render(request, 'telemetry/parameters.html', {'parameters': parameters})

def parameter_update(request, param_id):
    if request.method == 'POST':
        try:
            param = get_object_or_404(SensorParameter, id=param_id)
            data = json.loads(request.body)
            
            if 'active' in data:
                param.active = data['active']
            if 'include_in_ai' in data:
                param.include_in_ai = data['include_in_ai']
            if 'visualization' in data:
                param.visualization = data['visualization']
            if 'data_type' in data:
                param.data_type = data['data_type']
                
            param.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

from apps.ai_engine.analyzer import analyze_telemetry_window
from apps.ai_engine.weather import get_cached_weather
from datetime import datetime, timezone
from django.contrib.admin.views.decorators import staff_member_required

from apps.ai_engine.models import AnalysisResult
from django.contrib import messages

@staff_member_required
def telemetry_historical_analysis(request, device_id):
    device = get_object_or_404(Device, tb_device_id=device_id)
    
    # Get all rows (limit 10000 for safety, could be larger)
    rows, _ = get_all_telemetry_rows(str(device.tb_device_id), limit=10000, offset=0)
    
    # Sort rows chronologically
    rows = sorted(rows, key=lambda x: x['ts_ms'])
    
    # Window settings
    WINDOW_SIZE_MS = 10000
    
    results = []
    if rows:
        weather_data = get_cached_weather(device.id)
        
        # Group into 10-second tumbling windows
        current_window = []
        window_start_ms = rows[0]['ts_ms']
        
        for row in rows:
            if row['ts_ms'] - window_start_ms >= WINDOW_SIZE_MS:
                if current_window:
                    analysis = analyze_telemetry_window(current_window, weather_data)
                    # Format raw row timestamps
                    for r in current_window:
                        r['ts_str'] = datetime.fromtimestamp(r['ts_ms'] / 1000, tz=timezone.utc).strftime('%H:%M:%S.%f')[:-3]
                        
                    analysis['raw_rows'] = current_window
                    analysis['raw_ts'] = datetime.fromtimestamp((window_start_ms + WINDOW_SIZE_MS) / 1000, tz=timezone.utc)
                    analysis['start_time'] = datetime.fromtimestamp(window_start_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    analysis['end_time'] = analysis['raw_ts'].strftime('%Y-%m-%d %H:%M:%S')
                    results.append(analysis)
                window_start_ms += WINDOW_SIZE_MS
                current_window = [row]
            else:
                current_window.append(row)
                
        # Process the last window
        if current_window:
            analysis = analyze_telemetry_window(current_window, weather_data)
            
            for r in current_window:
                r['ts_str'] = datetime.fromtimestamp(r['ts_ms'] / 1000, tz=timezone.utc).strftime('%H:%M:%S.%f')[:-3]
                
            analysis['raw_rows'] = current_window
            analysis['raw_ts'] = datetime.fromtimestamp((window_start_ms + WINDOW_SIZE_MS) / 1000, tz=timezone.utc)
            analysis['start_time'] = datetime.fromtimestamp(window_start_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            analysis['end_time'] = analysis['raw_ts'].strftime('%Y-%m-%d %H:%M:%S')
            results.append(analysis)
            
    if request.method == 'POST' and request.POST.get('save_to_db') == 'true':
        saved_count = 0
        for res in results:
            AnalysisResult.objects.get_or_create(
                device=device,
                ts=res['raw_ts'],
                defaults={
                    'alarm': res.get('alarm', False),
                    'risk_level': res.get('risk_level', 'NORMAL'),
                    'risk_score': res.get('risk_score', 0.0),
                    'event_type': res.get('event_type', 'NORMAL'),
                    'vibration_mean': res.get('vibration_mean', 0.0),
                    'vibration_max': res.get('vibration_max', 0.0),
                    'vibration_min': res.get('vibration_min', 0.0),
                    'vibration_std': res.get('vibration_std', 0.0),
                    'persistence_ratio': res.get('persistence_ratio', 0.0),
                    'motion_samples': res.get('motion_samples', 0),
                    'motion_ratio': res.get('motion_ratio', 0.0),
                    'abnormal_samples': res.get('abnormal_samples', 0),
                    'total_samples': res.get('total_samples', 0),
                    'accel_magnitude': res.get('accel_magnitude', 0.0),
                    'accel_max': res.get('accel_max', 0.0),
                    'accel_mean': res.get('accel_mean', 0.0),
                    'gyro_magnitude': res.get('gyro_magnitude', 0.0),
                    'gyro_max': res.get('gyro_max', 0.0),
                    'gyro_mean': res.get('gyro_mean', 0.0),
                    'powercut': res.get('powercut', 0),
                    'cctv_cut': res.get('cctv_cut', 0),
                    'weather_state': res.get('weather_state', 'UNKNOWN'),
                    'storm_flag': res.get('storm_flag', False),
                    'rain_intensity': res.get('rain_intensity', 0.0),
                    'confidence': res.get('confidence', 1.0),
                    'alarm_reason': res.get('alarm_reason', ''),
                }
            )
            saved_count += 1
        messages.success(request, f"Saved {saved_count} historical analysis records to the database.")
            
    # Reverse so newest is first
    results.reverse()
    
    return render(request, 'telemetry/historical_analysis.html', {'device': device, 'results': results})


@staff_member_required
def analysis_export_csv(request, device_id):
    """Export all historical analysis windows + raw sensor rows as a single CSV."""
    device = get_object_or_404(Device, tb_device_id=device_id)

    rows, _ = get_all_telemetry_rows(str(device.tb_device_id), limit=10000, offset=0)
    rows = sorted(rows, key=lambda x: x['ts_ms'])

    WINDOW_SIZE_MS = 10000
    results = []
    if rows:
        weather_data = get_cached_weather(device.id)
        current_window = []
        window_start_ms = rows[0]['ts_ms']
        for row in rows:
            if row['ts_ms'] - window_start_ms >= WINDOW_SIZE_MS:
                if current_window:
                    analysis = analyze_telemetry_window(current_window, weather_data)
                    for r in current_window:
                        r['ts_str'] = datetime.fromtimestamp(r['ts_ms'] / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    analysis['raw_rows'] = current_window
                    analysis['start_time'] = datetime.fromtimestamp(window_start_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    analysis['end_time'] = datetime.fromtimestamp((window_start_ms + WINDOW_SIZE_MS) / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    results.append(analysis)
                window_start_ms += WINDOW_SIZE_MS
                current_window = [row]
            else:
                current_window.append(row)
        if current_window:
            analysis = analyze_telemetry_window(current_window, weather_data)
            for r in current_window:
                r['ts_str'] = datetime.fromtimestamp(r['ts_ms'] / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            analysis['raw_rows'] = current_window
            analysis['start_time'] = datetime.fromtimestamp(window_start_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            analysis['end_time'] = datetime.fromtimestamp((window_start_ms + WINDOW_SIZE_MS) / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            results.append(analysis)

    from django.utils.timezone import now as tz_now
    filename = f"{device.name}_analysis_{tz_now().strftime('%Y%m%d_%H%M%S')}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # ── Section 1: Analysis summary ──────────────────────────────────────────
    writer.writerow([
        '=== JOINIK ANALYSIS REPORT ===',
        f'Device: {device.name}',
        f'Export Time: {tz_now().strftime("%Y-%m-%d %H:%M:%S UTC")}',
        f'Total Windows: {len(results)}',
    ])
    writer.writerow([])
    writer.writerow([
        'Window #', 'Start Time', 'End Time', 'Risk Level', 'Risk Score',
        'Alarm', 'Event Type', 'Confidence', 'Alarm Reason',
        'Vib Mean', 'Vib Max', 'Vib Min', 'Vib Std',
        'Persistence Ratio', 'Motion Samples', 'Motion Ratio',
        'Abnormal Samples', 'Total Samples',
        'Accel Magnitude', 'Accel Max', 'Accel Mean',
        'Gyro Magnitude', 'Gyro Max', 'Gyro Mean',
        'Power Cut', 'CCTV Cut',
        'Weather State', 'Storm Flag', 'Rain Intensity',
    ])
    for idx, res in enumerate(results, 1):
        writer.writerow([
            idx,
            res.get('start_time', ''),
            res.get('end_time', ''),
            res.get('risk_level', 'NORMAL'),
            res.get('risk_score', 0.0),
            res.get('alarm', False),
            res.get('event_type', ''),
            res.get('confidence', 1.0),
            res.get('alarm_reason', ''),
            res.get('vibration_mean', 0.0),
            res.get('vibration_max', 0.0),
            res.get('vibration_min', 0.0),
            res.get('vibration_std', 0.0),
            res.get('persistence_ratio', 0.0),
            res.get('motion_samples', 0),
            res.get('motion_ratio', 0.0),
            res.get('abnormal_samples', 0),
            res.get('total_samples', 0),
            res.get('accel_magnitude', 0.0),
            res.get('accel_max', 0.0),
            res.get('accel_mean', 0.0),
            res.get('gyro_magnitude', 0.0),
            res.get('gyro_max', 0.0),
            res.get('gyro_mean', 0.0),
            res.get('powercut', 0),
            res.get('cctv_cut', 0),
            res.get('weather_state', 'UNKNOWN'),
            res.get('storm_flag', False),
            res.get('rain_intensity', 0.0),
        ])

    writer.writerow([])
    writer.writerow([])

    # ── Section 2: Raw sensor readings per window ─────────────────────────────
    writer.writerow(['=== RAW SENSOR DATA (Per Analysis Window) ==='])
    writer.writerow([])

    RAW_HEADERS = [
        'Window #', 'Window Start', 'Window End', 'Risk Level', 'Alarm',
        'Sample Time',
        'accel_x', 'accel_y', 'accel_z',
        'gyro_x', 'gyro_y', 'gyro_z',
        'hardness', 'motion', 'powercut', 'cctv_cut',
        'device_mac', 'scan_timestamp',
    ]
    writer.writerow(RAW_HEADERS)

    for idx, res in enumerate(results, 1):
        for raw in res.get('raw_rows', []):
            writer.writerow([
                idx,
                res.get('start_time', ''),
                res.get('end_time', ''),
                res.get('risk_level', 'NORMAL'),
                res.get('alarm', False),
                raw.get('ts_str', ''),
                raw.get('accel_x', ''),
                raw.get('accel_y', ''),
                raw.get('accel_z', ''),
                raw.get('gyro_x', ''),
                raw.get('gyro_y', ''),
                raw.get('gyro_z', ''),
                raw.get('hardness', raw.get('h', '')),
                raw.get('motion', ''),
                raw.get('powercut', ''),
                raw.get('cctv_cut', ''),
                raw.get('device_mac', ''),
                raw.get('scan_timestamp', ''),
            ])

    return response
