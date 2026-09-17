import time
import logging
from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from apps.devices.models import Device
from apps.core.tb_reader import get_latest_telemetry
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
            
        # -- Dynamic Parameter Auto-Detection --
        # Get currently known keys from Django DB
        from apps.telemetry.models import SensorParameter
        known_keys = set(SensorParameter.objects.values_list('key', flat=True))
        
        for key in latest.keys():
            if key not in known_keys:
                # Discovered a new key not in our Django DB!
                # Create it but quarantine it from AI to prevent poisoning
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
        
        # --- 1. Push Telemetry Update ---
        serializable_latest = {}
        for k, v in latest.items():
            serializable_latest[k] = {
                'value': v['value'],
                'ts': v['ts'].strftime('%H:%M:%S') if v['ts'] else '-'
            }
            
        async_to_sync(channel_layer.group_send)(
            f'device_{device_id_str}',
            {
                'type': 'telemetry_update',
                'data': serializable_latest
            }
        )
        
        # --- 2. Run AI Model ---
        risk_score = 5.0
        risk_level = 'NORMAL'
        trigger_alarm = False
        triggering_keys = []
        shap_values_dict = {}
        
        if ml_model and active_version:
            # Prepare feature array
            feature_array = []
            for f in active_version.feature_list:
                val = latest.get(f, {}).get('value', 0)
                if isinstance(val, bool):
                    val = int(val)
                feature_array.append(val)
                
            X_input = np.array([feature_array])
            
            try:
                # Predict probability of class 1 (anomaly/high risk)
                if hasattr(ml_model, 'predict_proba'):
                    probs = ml_model.predict_proba(X_input)[0]
                    anomaly_prob = probs[1] if len(probs) > 1 else probs[0]
                else:
                    # Fallback for models like SVM without proba enabled
                    pred = ml_model.predict(X_input)[0]
                    anomaly_prob = 1.0 if pred == 1 else 0.0
                    
                risk_score = anomaly_prob * 100
                
                if risk_score > 80:
                    risk_level = 'CRITICAL'
                    trigger_alarm = True
                elif risk_score > 60:
                    risk_level = 'HIGH'
                    trigger_alarm = True
                elif risk_score > 30:
                    risk_level = 'MEDIUM'
                elif risk_score > 15:
                    risk_level = 'LOW'
                    
                # Compute SHAP
                if explainer:
                    shaps = explainer.shap_values(X_input)
                    # For binary classification, shap_values might be a list [class0, class1] or just class1
                    if isinstance(shaps, list) and len(shaps) > 1:
                        shap_arr = shaps[1][0]
                    else:
                        shap_arr = shaps[0]
                        
                    for i, f in enumerate(active_version.feature_list):
                        shap_values_dict[f] = float(shap_arr[i])
                        # If highly contributory, add to triggering keys
                        if trigger_alarm and shap_arr[i] > 0.05:
                            triggering_keys.append(f)
                            
            except Exception as e:
                logger.error(f"Inference error on {device_id_str}: {e}")
                
        else:
            # Fallback Rule Engine
            vibration = latest.get('vibration_intensity', {}).get('value', 0)
            motion = latest.get('motion', {}).get('value', False)
            cctv_cut = latest.get('cctv_cut', {}).get('value', False)
            
            if vibration > 8:
                risk_score = 95.0
                risk_level = 'CRITICAL'
                trigger_alarm = True
                triggering_keys.append('vibration_intensity')
            elif motion and cctv_cut:
                risk_score = 85.0
                risk_level = 'HIGH'
                trigger_alarm = True
                triggering_keys.extend(['motion', 'cctv_cut'])
            elif motion:
                risk_score = 40.0
                risk_level = 'MEDIUM'
            elif vibration > 3:
                risk_score = 25.0
                risk_level = 'LOW'
            
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
                confidence=0.95,
                alarm_triggered=trigger_alarm,
                feature_snapshot={k: v['value'] for k, v in latest.items()},
                shap_values=shap_values_dict,
                model_version=active_version if active_version else None
            )
            
            if trigger_alarm:
                deadline = timezone.now() + timezone.timedelta(seconds=10)
                alarm_obj = Alarm.objects.create(
                    device=device,
                    risk_level=risk_level,
                    risk_score=risk_score,
                    ai_confidence=0.95,
                    triggering_keys=triggering_keys,
                    assessment=assessment,
                    status='PENDING',
                    cancellation_deadline=deadline
                )
                
                # Push global Dead-Hand modal trigger
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
                        'score': risk_score, # Legacy support
                        'level': risk_level, # Legacy support
                        'badge_class': device.risk_badge_class,
                        'shap': shap_values_dict,
                        
                        # Exact requested parameters from AI
                        'alarm': trigger_alarm,
                        'risk_level': risk_level,
                        'risk_score': risk_score,
                        'confidence': 95.0, # Placeholder until AI explicitly provides this
                        'alarm_reason': f"Anomalies detected in: {', '.join(triggering_keys)}" if trigger_alarm else "Normal behavior"
                    }
                }
            )
