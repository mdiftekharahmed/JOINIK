import time
import logging
from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from apps.devices.models import Device
from apps.core.tb_reader import get_latest_telemetry, get_telemetry_range
from apps.ai_engine.analyzer import analyze_telemetry_window
from apps.ai_engine.weather import get_cached_weather
from apps.alarms.models import Alarm
from .models import RiskAssessment, AIModelVersion, AnalysisResult
from django.utils import timezone
import joblib
import numpy as np
try:
    import shap
except ImportError:
    shap = None

logger = logging.getLogger(__name__)

_last_seen_ts = {}
# Cache the loaded ML model in memory so we don't load it from disk every 5s
_cached_model_id = None
_cached_model = None
_cached_explainer = None

def _get_active_model_and_explainer():
    global _cached_model_id, _cached_model, _cached_explainer
    active_version = AIModelVersion.objects.filter(is_active=True).first()
    if not active_version or not active_version.model_file:
        return None, None, None
        
    if _cached_model_id != active_version.id:
        try:
            _cached_model = joblib.load(active_version.model_file.path)
            _cached_model_id = active_version.id
            if shap:
                # Try to create a TreeExplainer if it's a tree-based model
                try:
                    _cached_explainer = shap.TreeExplainer(_cached_model)
                except Exception:
                    _cached_explainer = None # Fallback if not a tree model
            logger.info(f"Loaded new AI model: {active_version.version_tag}")
        except Exception as e:
            logger.error(f"Failed to load AI model {active_version.version_tag}: {e}")
            return None, None, None
            
    return active_version, _cached_model, _cached_explainer

@shared_task
def process_telemetry_and_risk():
    """
    Polls ThingsBoard DB for telemetry, runs ML inference via joblib,
    generates alarms, and pushes updates via WebSockets.
    """
    devices = Device.objects.all()
    channel_layer = get_channel_layer()
    
    active_version, ml_model, explainer = _get_active_model_and_explainer()

    for device in devices:
        device_id_str = str(device.tb_device_id)
        latest = get_latest_telemetry(device_id_str)
        if not latest:
            continue
            
        from apps.telemetry.models import SensorParameter
        known_keys = set(SensorParameter.objects.values_list('key', flat=True))
        
        for key in latest.keys():
            if key not in known_keys:
                SensorParameter.objects.create(
                    key=key,
                    display_name=key.replace('_', ' ').title(),
                    active=False,
                    include_in_ai=False
                )
                known_keys.add(key)
                logger.info(f"Auto-detected new telemetry key: {key} (Quarantined)")
            
        max_ts = None
        for key, data in latest.items():
            if data['ts']:
                if not max_ts or data['ts'] > max_ts:
                    max_ts = data['ts']
                    
        if not max_ts:
            continue
            
        last_ts = _last_seen_ts.get(device_id_str)
        if last_ts and max_ts <= last_ts:
            continue 
            
        _last_seen_ts[device_id_str] = max_ts
        
        # --- 10-Second Analysis Window ---
        now_ms = int(max_ts.timestamp() * 1000)
        start_ms = now_ms - 10000
        window_rows = get_telemetry_range(device_id_str, start_ms, now_ms, limit=1000)
        
        weather_data = get_cached_weather(device.id)
        analysis = analyze_telemetry_window(window_rows, weather_data)
        
        # --- 1. Push Telemetry Update ---
        serializable_latest = {}
        for k, v in latest.items():
            serializable_latest[k] = {
                'value': v['value'],
                'ts': v['ts'].strftime('%H:%M:%S') if v['ts'] else '-'
            }
            
        # Inject generated parameters into telemetry
        ts_str = max_ts.strftime('%H:%M:%S')
        for k, v in analysis.items():
            if k not in ['alarm', 'risk_level', 'risk_score', 'confidence', 'event_type', 'alarm_reason']:
                serializable_latest[k] = {
                    'value': v,
                    'ts': ts_str
                }
                
        async_to_sync(channel_layer.group_send)(
            f'device_{device_id_str}',
            {
                'type': 'telemetry_update',
                'data': serializable_latest
            }
        )
        # --- 2. Save AnalysisResult Ledger ---
        try:
            AnalysisResult.objects.create(
                device=device,
                ts=max_ts,
                alarm=analysis.get('alarm', 0),
                risk_level=analysis.get('risk_level', 'NORMAL'),
                risk_score=analysis.get('risk_score', 0.0),
                event_type=analysis.get('event_type', 'NORMAL'),
                vibration_mean=analysis.get('vibration_mean', 0.0),
                vibration_max=analysis.get('vibration_max', 0.0),
                vibration_min=analysis.get('vibration_min', 0.0),
                vibration_std=analysis.get('vibration_std', 0.0),
                persistence_ratio=analysis.get('persistence_ratio', 0.0),
                motion_samples=analysis.get('motion_samples', 0),
                motion_ratio=analysis.get('motion_ratio', 0.0),
                abnormal_samples=analysis.get('abnormal_samples', 0),
                total_samples=analysis.get('total_samples', 0),
                accel_magnitude=analysis.get('accel_magnitude', 0.0),
                accel_max=analysis.get('accel_max', 0.0),
                accel_mean=analysis.get('accel_mean', 0.0),
                gyro_magnitude=analysis.get('gyro_magnitude', 0.0),
                gyro_max=analysis.get('gyro_max', 0.0),
                gyro_mean=analysis.get('gyro_mean', 0.0),
                powercut=analysis.get('powercut', 0),
                cctv_cut=analysis.get('cctv_cut', 0),
                weather_state=analysis.get('weather_state', 'UNKNOWN'),
                storm_flag=analysis.get('storm_flag', False),
                rain_intensity=analysis.get('rain_intensity', 0.0),
                confidence=analysis.get('confidence', 1.0),
                alarm_reason=analysis.get('alarm_reason', ''),
            )
        except Exception as e:
            logger.error(f"Failed to save AnalysisResult for {device_id_str}: {e}")
        
        # --- 3. Extract Security Parameters ---
        risk_score = analysis['risk_score']
        risk_level = analysis['risk_level']
        trigger_alarm = analysis['alarm']
        triggering_keys = [analysis['event_type']] # Store the event type as triggering reason
        
        # --- 3. Save Risk Assessment & Alarm ---
        if risk_score != device.current_risk_score:
            device.current_risk_score = risk_score
            device.current_risk_level = risk_level
            device.save(update_fields=['current_risk_score', 'current_risk_level'])
            
            assessment = RiskAssessment.objects.create(
                device=device,
                ts=timezone.now(),
                risk_score=risk_score,
                risk_level=risk_level,
                confidence=analysis.get('confidence', 1.0),
                alarm_triggered=trigger_alarm,
                feature_snapshot=analysis,
                shap_values={},
                model_version=None
            )
            
            # User requirement: when medium and high risk detected there should be an alarm generated
            if trigger_alarm or risk_level in ['MEDIUM', 'HIGH', 'CRITICAL']:
                deadline = timezone.now() + timezone.timedelta(seconds=10)
                alarm_obj = Alarm.objects.create(
                    device=device,
                    risk_level=risk_level,
                    risk_score=risk_score,
                    ai_confidence=analysis.get('confidence', 1.0),
                    triggering_keys=triggering_keys,
                    assessment=assessment,
                    status='PENDING',
                    cancellation_deadline=deadline
                )
                
                # Send Web Notification
                async_to_sync(channel_layer.group_send)(
                    f'device_{device_id_str}',
                    {
                        'type': 'alarm_notification',
                        'data': {
                            'alarm_id': str(alarm_obj.id),
                            'device_name': device.name,
                            'risk_level': risk_level,
                            'risk_score': risk_score,
                            'reason': analysis.get('alarm_reason', 'Security event detected')
                        }
                    }
                )
                logger.warning(f"New Alarm {alarm_obj.id} triggered for {device_id_str}. Level: {risk_level}")
                
                async_to_sync(channel_layer.group_send)(
                    "global_alarms",
                    {
                        "type": "alarm_pending",
                        "alarm_data": {
                            "alarm_id": str(alarm_obj.id),
                            "device_name": device.name,
                            "triggering_keys": triggering_keys,
                            "risk_score": risk_score,
        return None, None, None
        
    if _cached_model_id != active_version.id:
        try:
            _cached_model = joblib.load(active_version.model_file.path)
            _cached_model_id = active_version.id
            if shap:
                # Try to create a TreeExplainer if it's a tree-based model
                try:
                    _cached_explainer = shap.TreeExplainer(_cached_model)
                except Exception:
                    _cached_explainer = None # Fallback if not a tree model
            logger.info(f"Loaded new AI model: {active_version.version_tag}")
        except Exception as e:
            logger.error(f"Failed to load AI model {active_version.version_tag}: {e}")
            return None, None, None
            
    return active_version, _cached_model, _cached_explainer

@shared_task
def process_telemetry_and_risk():
    """
    Polls ThingsBoard DB for telemetry, runs ML inference via joblib,
    generates alarms, and pushes updates via WebSockets.
    """
    devices = Device.objects.all()
    channel_layer = get_channel_layer()
    
    active_version, ml_model, explainer = _get_active_model_and_explainer()

    for device in devices:
        device_id_str = str(device.tb_device_id)
        latest = get_latest_telemetry(device_id_str)
        if not latest:
            continue
            
        from apps.telemetry.models import SensorParameter
        known_keys = set(SensorParameter.objects.values_list('key', flat=True))
        
        for key in latest.keys():
            if key not in known_keys:
                SensorParameter.objects.create(
                    key=key,
                    display_name=key.replace('_', ' ').title(),
                    active=False,
                    include_in_ai=False
                )
                known_keys.add(key)
                logger.info(f"Auto-detected new telemetry key: {key} (Quarantined)")
            
        max_ts = None
        for key, data in latest.items():
            if data['ts']:
                if not max_ts or data['ts'] > max_ts:
                    max_ts = data['ts']
                    
        if not max_ts:
            continue
            
        last_ts = _last_seen_ts.get(device_id_str)
        if last_ts and max_ts <= last_ts:
            continue 
            
        _last_seen_ts[device_id_str] = max_ts
        
        # --- Real-Time Single-Entry Analysis ---
        # Construct the current reading from live 'latest' telemetry
        current_reading = {'ts_ms': now_ms, 'timestamp': max_ts}
        for k, v in latest.items():
            current_reading[k] = v['value']
            
        pivoted_rows = [current_reading]
        
        weather_data = get_cached_weather(device.id)
        analysis = analyze_telemetry_window(pivoted_rows, weather_data)
        
        # --- 1. Push Telemetry Update ---
        serializable_latest = {}
        for k, v in latest.items():
            serializable_latest[k] = {
                'value': v['value'],
                'ts': v['ts'].strftime('%H:%M:%S') if v['ts'] else '-'
            }
            
        # Inject generated parameters into telemetry
        ts_str = max_ts.strftime('%H:%M:%S')
        for k, v in analysis.items():
            if k not in ['alarm', 'risk_level', 'risk_score', 'confidence', 'event_type', 'alarm_reason']:
                serializable_latest[k] = {
                    'value': v,
                    'ts': ts_str
                }
                
        async_to_sync(channel_layer.group_send)(
            f'device_{device_id_str}',
            {
                'type': 'telemetry_update',
                'data': serializable_latest
            }
        )
        # --- 2. Save AnalysisResult Ledger ---
        try:
            AnalysisResult.objects.create(
                device=device,
                ts=max_ts,
                alarm=analysis.get('alarm', 0),
                risk_level=analysis.get('risk_level', 'NORMAL'),
                risk_score=analysis.get('risk_score', 0.0),
                event_type=analysis.get('event_type', 'NORMAL'),
                vibration_mean=analysis.get('vibration_mean', 0.0),
                vibration_max=analysis.get('vibration_max', 0.0),
                vibration_min=analysis.get('vibration_min', 0.0),
                vibration_std=analysis.get('vibration_std', 0.0),
                persistence_ratio=analysis.get('persistence_ratio', 0.0),
                motion_samples=analysis.get('motion_samples', 0),
                motion_ratio=analysis.get('motion_ratio', 0.0),
                abnormal_samples=analysis.get('abnormal_samples', 0),
                total_samples=analysis.get('total_samples', 0),
                accel_magnitude=analysis.get('accel_magnitude', 0.0),
                accel_max=analysis.get('accel_max', 0.0),
                accel_mean=analysis.get('accel_mean', 0.0),
                gyro_magnitude=analysis.get('gyro_magnitude', 0.0),
                gyro_max=analysis.get('gyro_max', 0.0),
                gyro_mean=analysis.get('gyro_mean', 0.0),
                powercut=analysis.get('powercut', 0),
                cctv_cut=analysis.get('cctv_cut', 0),
                weather_state=analysis.get('weather_state', 'UNKNOWN'),
                storm_flag=analysis.get('storm_flag', False),
                rain_intensity=analysis.get('rain_intensity', 0.0),
                confidence=analysis.get('confidence', 1.0),
                alarm_reason=analysis.get('alarm_reason', ''),
            )
        except Exception as e:
            logger.error(f"Failed to save AnalysisResult for {device_id_str}: {e}")
        
        # --- 3. Extract Security Parameters ---
        risk_score = analysis['risk_score']
        risk_level = analysis['risk_level']
        trigger_alarm = analysis['alarm']
        triggering_keys = [analysis['event_type']] # Store the event type as triggering reason
        
        # --- 3. Save Risk Assessment & Alarm ---
        if risk_score != device.current_risk_score:
            device.current_risk_score = risk_score
            device.current_risk_level = risk_level
            device.save(update_fields=['current_risk_score', 'current_risk_level'])
            
            assessment = RiskAssessment.objects.create(
                device=device,
                ts=timezone.now(),
                risk_score=risk_score,
                risk_level=risk_level,
                confidence=analysis.get('confidence', 1.0),
                alarm_triggered=trigger_alarm,
                feature_snapshot=analysis,
                shap_values={},
                model_version=None
            )
            
            # User requirement: when medium and high risk detected there should be an alarm generated
            if trigger_alarm or risk_level in ['MEDIUM', 'HIGH', 'CRITICAL']:
                deadline = timezone.now() + timezone.timedelta(seconds=10)
                alarm_obj = Alarm.objects.create(
                    device=device,
                    risk_level=risk_level,
                    risk_score=risk_score,
                    ai_confidence=analysis.get('confidence', 1.0),
                    triggering_keys=triggering_keys,
                    assessment=assessment,
                    status='PENDING',
                    cancellation_deadline=deadline
                )
                
                # Send Web Notification
                async_to_sync(channel_layer.group_send)(
                    f'device_{device_id_str}',
                    {
                        'type': 'alarm_notification',
                        'data': {
                            'alarm_id': str(alarm_obj.id),
                            'device_name': device.name,
                            'risk_level': risk_level,
                            'risk_score': risk_score,
                            'reason': analysis.get('alarm_reason', 'Security event detected')
                        }
                    }
                )
                logger.warning(f"New Alarm {alarm_obj.id} triggered for {device_id_str}. Level: {risk_level}")
                
                async_to_sync(channel_layer.group_send)(
                    "global_alarms",
                    {
                        "type": "alarm_pending",
                        "alarm_data": {
                            "alarm_id": str(alarm_obj.id),
                            "device_name": device.name,
                            "triggering_keys": triggering_keys,
                            "risk_score": risk_score,
                            "deadline": alarm_obj.cancellation_deadline.isoformat()
                        }
                    }
                )
                
        # --- Send Web Notification ---
        async_to_sync(channel_layer.group_send)(
            f'device_{device_id_str}',
            {
                'type': 'risk_update',
                'data': {
                    'score': risk_score,
                    'level': risk_level,
                    'badge_class': device.risk_badge_class,
                    'alarm': trigger_alarm,
                    'confidence': analysis.get('confidence', 1.0) * 100, # Frontend expects percentage
                    'reason': analysis.get('alarm_reason', 'N/A'),
                    'shap': {},
                }
            }
        )
