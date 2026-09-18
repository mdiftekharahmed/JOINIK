import math
import statistics
import logging

logger = logging.getLogger(__name__)

# Configurable Thresholds
HARDNESS_MODERATE = 15
HARDNESS_HIGH = 40
ACCEL_MODERATE_ACTIVITY = 2.0  # Just an example baseline
GYRO_MODERATE_ACTIVITY = 100.0 # Example baseline

def analyze_telemetry_window(rows, weather_data=None):
    """
    Analyzes a complete window of telemetry data (e.g., 10 seconds).
    Returns EXACTLY the JOINIK security parameters and derived features.
    """
    total_samples = len(rows)
    if total_samples == 0:
        return _empty_result()
        
    device_mac = rows[0].get('device_mac', 'UNKNOWN')
    window_start = rows[0].get('timestamp', '')
    window_end = rows[-1].get('timestamp', '')
    
    hardnesses = []
    motions = []
    powercuts = []
    cctv_cuts = []
    
    accel_magnitudes = []
    gyro_magnitudes = []
    
    for row in rows:
        hardnesses.append(row.get('hardness', 0))
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

    # --- Vibration / Hardness Features ---
    vibration_max = max(hardnesses) if hardnesses else 0
    vibration_min = min(hardnesses) if hardnesses else 0
    vibration_mean = sum(hardnesses) / total_samples if total_samples else 0
    vibration_std = statistics.stdev(hardnesses) if total_samples > 1 else 0
    
    abnormal_samples = sum(1 for v in hardnesses if v > HARDNESS_MODERATE)
    persistence_ratio = abnormal_samples / total_samples if total_samples > 0 else 0
    
    # --- Motion Features ---
    motion_samples = sum(1 for m in motions if m)
    motion_ratio = motion_samples / total_samples if total_samples > 0 else 0
    any_motion = any(motions)
    
    # --- Infrastructure Features ---
    any_powercut = any(powercuts)
    any_cctv_cut = any(cctv_cuts)
    
    # --- Accelerometer Features ---
    accel_max = max(accel_magnitudes) if accel_magnitudes else 0
    accel_mean = sum(accel_magnitudes) / total_samples if total_samples else 0
    persistent_accel = (accel_mean > ACCEL_MODERATE_ACTIVITY)
    
    # --- Gyroscope Features ---
    gyro_max = max(gyro_magnitudes) if gyro_magnitudes else 0
    gyro_mean = sum(gyro_magnitudes) / total_samples if total_samples else 0
    persistent_gyro = (gyro_mean > GYRO_MODERATE_ACTIVITY)
    
    # --- Weather Context ---
    weather_state = "Normal"
    storm_flag = False
    rain_intensity = 0
    if weather_data:
        weather_state = weather_data.get('weather_state', 'Normal')
        storm_flag = weather_data.get('storm_flag', False)
        rain_intensity = weather_data.get('precipitation', 0)
        
    # ==========================================
    # RULE-BASED CLASSIFICATION & SCORE
    # ==========================================
    
    event_type = "NORMAL_MOTION" if any_motion else "NORMAL"
    alarm = 0
    risk_level = "NORMAL"
    risk_score = 0.0
    confidence = min(1.0, total_samples / 10.0)  # Lower confidence if few samples in 10s
    alarm_reason = "Normal behavior detected"
    
    # Helper to calculate base risk score based on multi-sensor evidence
    evidence_score = 0
    evidence_score += (persistence_ratio * 30)  # up to 30 for persistent vibration
    if persistent_accel: evidence_score += 15
    if persistent_gyro: evidence_score += 15
    if any_motion: evidence_score += 10
    if any_powercut: evidence_score += 15
    if any_cctv_cut: evidence_score += 15
    
    # Scenario Cases (from 1 to 7)
    
    # CASE 7: COORDINATED MULTI-SENSOR EVENT
    if persistence_ratio > 0.30 and (persistent_accel or persistent_gyro) and any_motion and any_powercut and any_cctv_cut:
        event_type = "POSSIBLE_INTRUSION"
        alarm = 1
        risk_level = "CRITICAL"
        risk_score = 95.0
        alarm_reason = "Persistent vibration, motion, power interruption and CCTV interruption detected"
        
    # CASE 5: POSSIBLE TAMPERING
    elif persistence_ratio > 0.30 and any_motion and (persistent_accel or persistent_gyro):
        event_type = "POSSIBLE_TAMPERING"
        alarm = 1
        risk_score = min(85.0, 50.0 + evidence_score)
        risk_level = "HIGH"
        alarm_reason = "Persistent abnormal vibration detected with motion activity"
        
    # CASE 6: POWER + CCTV INTERRUPTION (no physical)
    elif any_powercut and any_cctv_cut and persistence_ratio < 0.10:
        event_type = "INFRASTRUCTURE_INTERRUPTION"
        alarm = 0
        risk_score = 30.0
        risk_level = "MEDIUM"
        alarm_reason = "Power and CCTV interruption detected without physical sensor evidence"
        
    # CASE 3: ENVIRONMENTAL DISTURBANCE
    elif persistence_ratio > 0.10 and storm_flag and not any_motion and not any_cctv_cut and not any_powercut:
        event_type = "ENVIRONMENTAL_DISTURBANCE"
        alarm = 0
        risk_score = 25.0
        risk_level = "LOW"
        alarm_reason = "Persistent physical activity detected during storm conditions"
        
    # CASE 4: SUSTAINED PHYSICAL ACTIVITY
    elif persistence_ratio > 0.20 or persistent_accel or persistent_gyro:
        event_type = "SUSTAINED_PHYSICAL_ACTIVITY"
        alarm = 0
        risk_score = min(60.0, 30.0 + evidence_score)
        risk_level = "MEDIUM" if risk_score > 40 else "LOW"
        alarm_reason = "Persistent physical activity detected"
        
    # CASE 2: ISOLATED PHYSICAL IMPACT
    elif vibration_max > HARDNESS_HIGH and persistence_ratio < 0.10 and not any_motion:
        event_type = "PHYSICAL_IMPACT"
        alarm = 0
        risk_score = 20.0
        risk_level = "LOW"
        alarm_reason = "Strong isolated vibration detected without sustained motion"
        
    # CASE 1: NORMAL / QUIET — compute a real score from the raw sensor magnitudes
    else:
        # Derive a continuous baseline score from actual sensor activity (0–20 range)
        # accel_mean hovering around ~1.0g (gravity) is normal; deviations from 1g = activity
        accel_deviation = abs(accel_mean - 1.0)            # 0 = perfect static, higher = movement
        norm_accel = min(accel_deviation / 1.0, 1.0)       # normalise to 0–1 (1.0g deviation = max)
        norm_gyro  = min(gyro_mean / 10.0, 1.0)            # 10 deg/s = max for NORMAL case
        norm_vib   = min(vibration_mean / HARDNESS_MODERATE, 1.0)
        norm_motion = motion_ratio                          # already 0–1
        
        baseline_score = (
            norm_accel  * 8.0 +   # up to  8 pts from accel deviation
            norm_gyro   * 6.0 +   # up to  6 pts from gyro
            norm_vib    * 4.0 +   # up to  4 pts from vibration
            norm_motion * 2.0     # up to  2 pts from any motion samples
        )
        risk_score = round(min(baseline_score, 20.0), 1)
        
        if risk_score >= 10.0:
            risk_level = "LOW"
            alarm_reason = "Slight sensor activity — within acceptable limits"
        else:
            risk_level = "NORMAL"
            alarm_reason = "All sensors within normal range"

    # Adjust score if weather is stormy (unless it's an infrastructure or confirmed tamper event)
    if storm_flag and event_type not in ["POSSIBLE_INTRUSION", "INFRASTRUCTURE_INTERRUPTION"]:
        risk_score = max(0.0, risk_score - 10.0)
        
    # Ensure score bounds
    risk_score = max(0.0, min(100.0, risk_score))
        
    return {
        # Primary JOINIK Security Parameters
        "device_mac": device_mac,
        "timestamp": window_end, # use the end of the window as the primary timestamp
        "alarm": alarm,
        "risk_level": risk_level,
        "risk_score": round(risk_score, 1),
        "confidence": round(confidence, 2),
        "event_type": event_type,
        "alarm_reason": alarm_reason,
        "persistence_ratio": round(persistence_ratio, 2),
        
        # Additional Derived Features
        "vibration_mean": round(vibration_mean, 2),
        "vibration_max": vibration_max,
        "vibration_min": vibration_min,
        "vibration_std": round(vibration_std, 2),
        "abnormal_samples": abnormal_samples,
        "total_samples": total_samples,
        "motion_samples": motion_samples,
        "motion_ratio": round(motion_ratio, 2),
        "accel_magnitude": round(accel_mean, 2), # maintaining backward compatibility
        "accel_max": round(accel_max, 2),
        "accel_mean": round(accel_mean, 2),
        "gyro_magnitude": round(gyro_mean, 2), # maintaining backward compatibility
        "gyro_max": round(gyro_max, 2),
        "gyro_mean": round(gyro_mean, 2),
        "powercut": 1 if any_powercut else 0,
        "cctv_cut": 1 if any_cctv_cut else 0,
        "window_start": window_start,
        "window_end": window_end,
        "weather_state": weather_state,
        "storm_flag": storm_flag,
        "rain_intensity": rain_intensity
    }

def _empty_result():
    return {
        "device_mac": "UNKNOWN",
        "timestamp": "",
        "alarm": 0,
        "risk_level": "NORMAL",
        "risk_score": 0.0,
        "confidence": 1.0,
        "event_type": "NO_DATA",
        "alarm_reason": "No data in window",
        "persistence_ratio": 0.0,
        "vibration_mean": 0,
        "vibration_max": 0,
        "vibration_min": 0,
        "vibration_std": 0,
        "abnormal_samples": 0,
        "total_samples": 0,
        "motion_samples": 0,
        "motion_ratio": 0.0,
        "accel_magnitude": 0.0,
        "accel_max": 0.0,
        "accel_mean": 0.0,
        "gyro_magnitude": 0.0,
        "gyro_max": 0.0,
        "gyro_mean": 0.0,
        "powercut": 0,
        "cctv_cut": 0,
        "window_start": "",
        "window_end": "",
        "weather_state": "UNKNOWN",
        "storm_flag": False,
        "rain_intensity": 0
    }
