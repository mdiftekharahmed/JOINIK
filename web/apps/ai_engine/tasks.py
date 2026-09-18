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
from .models import RiskAssessment, AIModelVersion
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
        
        # --- 2. Extract Security Parameters ---
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
                confidence=analysis['confidence'],
                alarm_triggered=trigger_alarm,
                feature_snapshot=analysis,
                shap_values={},
                model_version=None
            )
            
            if trigger_alarm:
                deadline = timezone.now() + timezone.timedelta(seconds=10)
                alarm_obj = Alarm.objects.create(
                    device=device,
                    risk_level=risk_level,
                    risk_score=risk_score,
                    ai_confidence=analysis['confidence'],
                    triggering_keys=triggering_keys,
                    assessment=assessment,
                    status='PENDING',
                    cancellation_deadline=deadline
                )
                
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
                
            async_to_sync(channel_layer.group_send)(
                f'device_{device_id_str}',
                {
                    'type': 'risk_update',
                    'data': {
                        'score': risk_score,
                        'level': risk_level,
                        'badge_class': device.risk_badge_class,
                        'shap': {},
                        'alarm': trigger_alarm,
                        'risk_level': risk_level,
                        'risk_score': risk_score,
                        'confidence': analysis['confidence'],
                        'alarm_reason': analysis['alarm_reason']
                    }
                }
            )
