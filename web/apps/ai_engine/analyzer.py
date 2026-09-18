import math
import logging

logger = logging.getLogger(__name__)

MODERATE_VIBRATION = 15
HIGH_VIBRATION = 40

def analyze_telemetry_window(rows, weather_data=None):
    """
    Analyzes a window of telemetry data (e.g., 10 seconds).
    Returns a dictionary of generated security parameters.
    """
    total_samples = len(rows)
    if total_samples == 0:
        return _empty_result()
        
    vibrations = []
    motions = []
    accel_magnitudes = []
    gyro_magnitudes = []
    powercuts = []
    cctv_cuts = []
    
    for row in rows:
        vibration = row.get('vibration_intensity', 0)
        vibrations.append(vibration)
        
        motions.append(bool(row.get('motion', False)))
        powercuts.append(bool(row.get('powercut', False)))
        cctv_cuts.append(bool(row.get('cctv_cut', False)))
        
        ax = row.get('accel_x', 0)
        ay = row.get('accel_y', 0)
        az = row.get('accel_z', 0)
        accel_magnitudes.append(math.sqrt(ax**2 + ay**2 + az**2))
        
        gx = row.get('gyro_x', 0)
        gy = row.get('gyro_y', 0)
        gz = row.get('gyro_z', 0)
        gyro_magnitudes.append(math.sqrt(gx**2 + gy**2 + gz**2))

    vibration_max = max(vibrations)
    vibration_min = min(vibrations)
    vibration_mean = sum(vibrations) / total_samples
    
    abnormal_samples = sum(1 for v in vibrations if v > MODERATE_VIBRATION)
    persistence_ratio = abnormal_samples / total_samples if total_samples > 0 else 0
    motion_ratio = sum(1 for m in motions if m) / total_samples if total_samples > 0 else 0
    
    # Calculate base boolean states
    any_motion = any(motions)
    any_powercut = any(powercuts)
    any_cctv_cut = any(cctv_cuts)
    
    # Initial classification
    alarm = False
    risk_level = 'NORMAL'
    risk_score = 0.0
    confidence = 0.8
    event_type = 'NORMAL'
    alarm_reason = 'Normal behavior'
    
    storm_flag = weather_data and weather_data.get('storm_flag', False)
    
    if persistence_ratio > 0.60:
        if any_motion and any_powercut and any_cctv_cut:
            event_type = 'POSSIBLE_INTRUSION'
            risk_level = 'CRITICAL'
            risk_score = 95.0
            alarm = True
            alarm_reason = 'Multiple independent signals indicate intrusion (persistent vibration + motion + infrastructure cuts)'
        elif any_motion:
            event_type = 'POSSIBLE_TAMPERING'
            risk_level = 'HIGH'
            risk_score = 75.0
            alarm = True
            alarm_reason = 'Persistent tampering detected with motion'
        else:
            if storm_flag:
                event_type = 'ENVIRONMENTAL_DISTURBANCE'
                risk_level = 'LOW'
                risk_score = 25.0
                alarm = False
                alarm_reason = 'Persistent vibration likely caused by storm'
            else:
                event_type = 'SUSTAINED_ABNORMAL_ACTIVITY'
                risk_level = 'MEDIUM'
                risk_score = 55.0
                alarm = False
                alarm_reason = 'Persistent vibration without motion'
    elif persistence_ratio > 0.30:
        event_type = 'SUSTAINED_ABNORMAL_ACTIVITY'
        risk_level = 'MEDIUM'
        risk_score = 45.0
        alarm = False
        alarm_reason = 'Sustained abnormal activity detected'
    elif persistence_ratio > 0.10:
        event_type = 'INTERMITTENT_DISTURBANCE'
        risk_level = 'LOW'
        risk_score = 20.0
        alarm = False
        alarm_reason = 'Intermittent disturbance detected'
    else:
        # Check for short physical impact
        if vibration_max > HIGH_VIBRATION and not any_motion:
            event_type = 'PHYSICAL_IMPACT'
            risk_level = 'MEDIUM'
            risk_score = 35.0
            alarm = False
            alarm_reason = 'Sudden physical impact detected'
        elif any_motion:
            event_type = 'NORMAL_MOTION'
            risk_level = 'LOW'
            risk_score = 10.0
            alarm = False
            alarm_reason = 'Normal motion detected'
            
    # Independent infrastructure check
    if any_powercut and any_cctv_cut and persistence_ratio < 0.10:
        event_type = 'INFRASTRUCTURE_INTERRUPTION'
        risk_level = 'MEDIUM'
        risk_score = 30.0
        alarm = False
        alarm_reason = 'Power and CCTV failure without physical evidence'
        
    return {
        'alarm': alarm,
        'risk_level': risk_level,
        'risk_score': risk_score,
        'confidence': confidence,
        'event_type': event_type,
        'alarm_reason': alarm_reason,
        'vibration_mean': round(vibration_mean, 2),
        'vibration_max': vibration_max,
        'vibration_min': vibration_min,
        'abnormal_samples': abnormal_samples,
        'total_samples': total_samples,
        'persistence_ratio': round(persistence_ratio, 2),
        'motion_ratio': round(motion_ratio, 2),
        'accel_magnitude': round(sum(accel_magnitudes) / total_samples, 2),
        'gyro_magnitude': round(sum(gyro_magnitudes) / total_samples, 2),
    }

def _empty_result():
    return {
        'alarm': False,
        'risk_level': 'NORMAL',
        'risk_score': 0.0,
        'confidence': 1.0,
        'event_type': 'NO_DATA',
        'alarm_reason': 'No data in window',
        'vibration_mean': 0,
        'vibration_max': 0,
        'vibration_min': 0,
        'abnormal_samples': 0,
        'total_samples': 0,
        'persistence_ratio': 0,
        'motion_ratio': 0,
        'accel_magnitude': 0,
        'gyro_magnitude': 0,
    }
