# JOINIK — IoT Security Platform
## Planning Document

> Last updated: 2026-09-17

---

## Vision

> **ThingsBoard = IoT backend**
> **Django web = human-facing security platform + AI decision layer**

JOINIK is a modular, AI-augmented IoT security platform. The Django layer reads directly
from the ThingsBoard PostgreSQL database, exposes a rich human-facing dashboard, runs the
AI risk model, manages alarms, and provisions new devices back into ThingsBoard via its REST API.

---

## Environment (Confirmed)

| Item | Value |
|---|---|
| ThingsBoard host | 100.82.190.70:8080 |
| ThingsBoard DB | 100.82.190.70:5432 · db=thingsboard · user=postgres · pass=postgres |
| ThingsBoard admin | sysadmin@thingsboard.org / Whatpassw0rd???? |
| ThingsBoard API | ✅ JWT auth confirmed working |
| Local PostgreSQL | localhost:5432 · user=postgres · pass=postgres (v18.4 running) |
| Django DB name | joinik (to be created on localhost) |
| Python | 3.13.14 |
| Django | to be installed |
| Production plan | Separate VM on Proxmox host (later) |
| Map | SVG floorplan (TBD — no GPS needed for now) |

---

## Known Data (From ThingsBoard DB)

### Devices
| Name | ThingsBoard UUID | MAC |
|---|---|---|
| JOINIK_Module_01 | 432bd840-b20a-11f1-be96-b92a8fbab147 | 68:09:47:4E:75:F0 |
| Water Level | ffb31000-9d47-11f1-bb87-836555c85dc0 | — |

### Firmware (joinik.ino) — sends every 2 seconds via HTTP POST
```
Fields sent: timestamp, device_mac, vibration_intensity, motion,
             accel_x/y/z, gyro_x/y/z, temperature, humidity, power_cut, cctv_cut
```

### ThingsBoard `ts_kv` Schema
| Column | Type | Notes |
|---|---|---|
| entity_id | uuid | maps to device.id |
| key | integer | maps to key_dictionary.key_id |
| ts | bigint | Unix milliseconds UTC |
| bool_v / long_v / dbl_v / str_v | mixed | value in correct column |

### JOINIK_Module_01 Sensor Keys (confirmed in DB)
| Key | Type | Range | Description |
|---|---|---|---|
| accel_x / y / z | double | −2.0 – +2.0 g | Accelerometer |
| gyro_x / y / z | double | −250 – +250 dps | Gyroscope |
| motion | long (0/1) | 0 or 1 | PIR motion |
| vibration_intensity | long | 0–100 | Vibration level |
| humidity | double | 0.0–100.0 % | Relative humidity |
| temperature | double | °C | Ambient temperature |
| power_cut | long (0/1) | 0 or 1 | Power interruption |
| cctv_cut | long (0/1) | 0 or 1 | CCTV signal cut |
| device_mac | string | — | Device MAC address |
| timestamp | string | — | Device local timestamp |

### ThingsBoard `attribute_kv` for device activity
| attribute_key | key name | Meaning |
|---|---|---|
| 43 | active | bool — is device currently online? |
| 45 | lastActivityTime | long — last heartbeat Unix ms |
| 44 | inactivityAlarmTime | long |

---

## Architecture

```
ESP32 (joinik.ino)
   │  HTTP POST JSON every 2 s
   ▼
ThingsBoard (100.82.190.70:8080)
   │                    ▲
   │  Direct SQL read   │  REST API — device provisioning
   ▼                    │
Django (localhost → Proxmox VM later)
   │
   ├── REST API (DRF)
   ├── WebSocket (Django Channels) ──→ Live dashboard push
   ├── Celery + Redis ──────────────→ AI scoring, notifications
   └── Django PostgreSQL (joinik) ──→ Alarms, AI results, reviews, audit
```

### Key Rules
- Django **reads** telemetry from ThingsBoard PostgreSQL (`ts_kv`, `attribute_kv`)
- Django **never writes** to ThingsBoard's `ts_kv`
- Django **provisions** devices via ThingsBoard REST API (using stored JWT)
- Django stores its own data (alarms, AI, reviews, audit) in **local `joinik` DB**

---

## Tech Stack

| Layer | Technology |
|---|---|
| IoT Backend | ThingsBoard Community (running) |
| Firmware | ESP32 Arduino (running) |
| Web Framework | Django 5 |
| REST API | Django REST Framework |
| Real-time push | Django Channels + Redis (WebSocket) |
| AI / ML | scikit-learn — Random Forest |
| AI explainability | SHAP |
| Frontend | Django Templates + Vanilla JS + Chart.js + Lucide icons |
| Styling | Vanilla CSS (dark, glassmorphism, Inter font) |
| Django DB | PostgreSQL — local `joinik` database |
| Cache / Broker | Redis |
| Task Queue | Celery |
| Map | SVG floorplan (Leaflet.js later if GPS added) |
| Fonts | Google Fonts — Inter |

---

## Navigation

```
JOINIK
│
├── /                     Dashboard          — "what is happening right now?"
├── /devices/             Device List        — grid + Add Device button
├── /devices/<id>/        Device Detail      — sensors, risk, alarms, timeline
├── /live/                Live Telemetry     — WebSocket real-time stream
├── /events/              Event Timeline     — clustered human-readable log
├── /alarms/              Alarm Center       — active + history
├── /alarms/<id>/         Incident Report    — investigation + human review
├── /ai/                  AI Risk Center     — score, SHAP explanation, history
├── /analytics/           Historical Stats   — weekly/monthly charts
├── /map/                 Map / Floorplan    — device locations + risk badges
├── /data/                Data Export        — CSV / JSON / training set
├── /notifications/       Notification Config
└── /admin-panel/
      ├── /users/
      ├── /organizations/
      ├── /sensors/        — dynamic sensor config
      └── /ai-model/       — model versions, retrain, rollback
```

---

## Django Project Structure

```
web/
├── manage.py
├── requirements.txt
├── .env                  ← secrets (never committed)
│
├── config/
│   ├── settings.py       ← two DB connections: default + thingsboard (read-only)
│   ├── urls.py
│   ├── asgi.py           ← Django Channels entry
│   └── celery.py
│
├── apps/
│   ├── core/             ← TB DB connector, shared utils, context processors
│   ├── accounts/         ← User, Organization, Role (SYSTEM_ADMIN etc.)
│   ├── devices/          ← Device model, TB provisioning service
│   ├── telemetry/        ← ts_kv reader, WebSocket consumer, SensorParameter
│   ├── alarms/           ← Alarm, HumanVerification, IncidentReport
│   ├── ai_engine/        ← RiskAssessment, AIModelVersion, Celery tasks
│   ├── analytics/        ← aggregation, export
│   ├── notifications/    ← NotificationRule, email/Telegram dispatch
│   └── audit/            ← AuditLog
│
├── static/
│   ├── css/style.css     ← global dark theme
│   ├── js/
│   │   ├── dashboard.js
│   │   ├── live.js       ← WebSocket client
│   │   ├── charts.js     ← Chart.js wrappers + auto-viz logic
│   │   └── map.js
│   └── icons/
│
└── templates/
    ├── base.html         ← sidebar, topbar, toast notifications
    ├── dashboard.html
    ├── devices/
    │   ├── list.html
    │   └── detail.html
    ├── telemetry/live.html
    ├── events/timeline.html
    ├── alarms/
    │   ├── center.html
    │   └── incident.html
    ├── ai/risk_center.html
    ├── analytics/index.html
    ├── map/index.html
    ├── data/export.html
    └── admin_panel/
        ├── sensors.html
        ├── ai_model.html
        ├── users.html
        └── organizations.html
```

---

## Django Models (local `joinik` DB)

### `accounts` app
```python
Organization(id, name, description, created_at)

UserProfile(
    user → auth.User,
    organization → Organization,
    role,           # SYSTEM_ADMIN / ORG_ADMIN / OPERATOR / VIEWER
)
```

### `devices` app
```python
Device(
    id,
    tb_device_id,        # ThingsBoard UUID e.g. "432bd840-b20a-11f1-be96-b92a8fbab147"
    name,                # "JOINIK_Module_01"
    mac_address,         # "68:09:47:4E:75:F0"
    organization → Organization,
    location_name,       # "Shop 01 — Front Door"
    location_x,          # 0.0–1.0 for SVG floorplan
    location_y,
    firmware_version,
    tb_access_token,     # access token shown to user for ESP32 flashing
    added_at,
    notes,
)
```

### `telemetry` app
```python
SensorParameter(
    key,                 # "accel_x" — matches key_dictionary.key
    display_name,        # "Acceleration X"
    data_type,           # BOOLEAN / NUMERIC / STRING
    unit,                # "g" / "°C" / "%" / "dps"
    visualization,       # AUTO / GAUGE / GRAPH_3AXIS / STATUS / BATTERY / BAR
    danger_condition,    # Python-safe expression e.g. "value > 2.0"
    include_in_ai,       # bool
    active,              # bool
    created_at,
)
# NOTE: ts_kv rows are NEVER stored in Django DB — always read from ThingsBoard
```

### `alarms` app
```python
Alarm(
    id,
    device → Device,
    tb_alarm_id,         # ThingsBoard alarm UUID (if TB also raised one)
    risk_level,          # LOW / MEDIUM / HIGH / CRITICAL
    risk_score,          # 0.0–100.0
    ai_confidence,       # 0.0–1.0
    triggered_at,
    acknowledged_at,
    acknowledged_by → User,
    resolved_at,
    resolved_by → User,
    status,              # ACTIVE / ACKNOWLEDGED / RESOLVED / FALSE_ALARM
    notes,
    triggering_keys,     # JSONField — ["motion", "cctv_cut", "accel_x"]
    assessment → RiskAssessment,
)

HumanVerification(
    alarm → Alarm,
    verdict,             # CONFIRMED / FALSE_ALARM / MAINTENANCE / UNKNOWN
    verified_by → User,
    verified_at,
    notes,
)
```

### `ai_engine` app
```python
RiskAssessment(
    id,
    device → Device,
    ts,                  # datetime — timestamp of the scored reading
    risk_score,          # 0.0–100.0
    risk_level,          # LOW / MEDIUM / HIGH / CRITICAL
    confidence,          # 0.0–1.0
    alarm_triggered,     # bool — score >= 75
    feature_snapshot,    # JSONField — sensor values used as input
    shap_values,         # JSONField — per-feature SHAP contribution
    model_version → AIModelVersion,
)

AIModelVersion(
    id,
    version_tag,         # "v1.0"
    model_file,          # FileField — .pkl path
    training_samples,
    feature_list,        # JSONField
    trained_at,
    is_active,           # only one active at a time
    notes,
)
```

### `audit` app
```python
AuditLog(
    id,
    user → User,
    action,              # "acknowledged_alarm" / "added_device" / "retrained_model"
    target_type,         # "Alarm" / "Device" / "AIModelVersion"
    target_id,
    detail,
    timestamp,
)
```

---

## ThingsBoard Integration

### Reading (direct SQL — no ORM)
```python
# apps/core/tb_reader.py
class ThingsBoardReader:
    def get_latest_telemetry(device_id: str) -> dict
    def get_telemetry_range(device_id, keys, start_ms, end_ms) -> list[dict]
    def get_device_online(device_id: str) -> bool
    def get_last_activity(device_id: str) -> datetime
    def get_all_devices() -> list[dict]      # from device table
    def get_alarms(device_id: str) -> list   # from alarm table
```

### Writing (REST API — `apps/core/tb_api.py`)
```python
class ThingsBoardAPI:
    def login() -> str                              # returns JWT
    def create_device(name, type) -> dict           # POST /api/device
    def get_device_credentials(device_id) -> str    # GET /api/device/{id}/credentials
    def delete_device(device_id)                    # DELETE /api/device/{id}
```

### Add Device Flow
```
User fills form: name, organization, location
      │
      ▼
Django: ThingsBoardAPI.create_device(name)
      │
      ▼
ThingsBoard returns: tb_device_id + access_token
      │
      ▼
Django saves: Device(tb_device_id=..., tb_access_token=...)
      │
      ▼
UI shows the access token → user flashes it onto ESP32
      │
      ▼
ESP32 sends telemetry → ThingsBoard stores in ts_kv
      │
      ▼
Django reads ts_kv → dashboard shows live data
```

---

## AI Risk Engine

### Input Features (per telemetry reading)
```
motion              0 or 1
cctv_cut            0 or 1
power_cut           0 or 1
vibration_intensity 0–100
accel_magnitude     sqrt(x²+y²+z²)   computed
gyro_magnitude      sqrt(x²+y²+z²)   computed
humidity            0.0–100.0
temperature         float °C
```

### Output
```
risk_score    0–100 float
risk_level    LOW (0–24) / MEDIUM (25–49) / HIGH (50–74) / CRITICAL (75–100)
confidence    0.0–1.0
alarm         bool  (True when risk_score >= 75)
shap_values   dict  per-feature SHAP contribution
```

### Pipeline
```
New ts_kv row arrives (detected by Celery beat polling)
      │
      ▼
Feature extractor builds input vector
      │
      ▼
Active AIModelVersion.predict(features)
      │
      ▼
RiskAssessment saved to Django DB
      │
      ▼
If alarm_triggered:  Alarm created → Notification dispatched
```

### Risk Thresholds
```
0  – 24   → LOW       (log only)
25 – 49   → MEDIUM    (log only)
50 – 74   → HIGH      (alarm created, no push notification by default)
75 – 100  → CRITICAL  (alarm created + notification sent)
```

---

## Dynamic Sensor System

New keys in `ts_kv` auto-register as `SensorParameter` rows with smart defaults.

### Auto-Visualization Rules
| Key Pattern | Auto Viz |
|---|---|
| `*_x`, `*_y`, `*_z` sharing prefix | 3-axis line graph |
| `*_cut`, `motion`, `power_*` | Status indicator (ON / OFF) |
| `temperature`, `humidity` | Gauge + time graph |
| `battery*` | Battery gauge |
| `vibration*` | Animated bar meter |
| Unknown numeric (long_v / dbl_v) | Sparkline + value card |
| Unknown boolean (bool_v) | Status badge |

---

## Pages — Spec

### `/` Dashboard
- Stat cards: Total Devices · Online · Offline · Active Alarms · Highest Risk · AI Status
- Live Security Status table (device → risk bar → score %) — auto-refresh every 5 s
- Recent Events feed (last 10, timestamp · device · triggers · level)
- Device Health mini-list (online badge · last seen · battery if available)

### `/devices/` Device List
- Grid of device cards: name · MAC · online badge · last seen · risk badge · sensor count
- **"Add Device"** button → modal → ThingsBoard API → save Device → show access token

### `/devices/<id>/` Device Detail
- Header: name, MAC, status, last seen, firmware, location
- Dynamic sensor grid (SensorParameter-driven, current values from ts_kv_latest)
- Risk gauge + current score
- Recent alarms list (last 5)
- Event mini-timeline for this device

### `/live/` Live Telemetry
- Device selector dropdown
- WebSocket push (Channels consumer → polls ts_kv every 2 s)
- Time range: 1 min / 5 min / 1 h / 24 h / Custom
- Per-sensor panel (auto-rendered from SensorParameter)
- Pause / Resume toggle

### `/events/` Event Timeline
- Readings clustered by time gap > 60 s = new event
- Event header: timestamp + device + AI decision badge
- Sensor triggers listed per event
- Filters: device, risk level, date range
- Click event → Incident Report

### `/alarms/` Alarm Center
- ACTIVE section: grouped CRITICAL → HIGH → MEDIUM → LOW
- HISTORY section with date/device/level filters
- Per alarm: device · level · time · confidence · triggering keys · Ack / Resolve buttons

### `/alarms/<id>/` Incident Report
- Full card: device, time, risk score, confidence, AI decision
- Triggering conditions table: sensor → value → status
- Sub-timeline: individual ts_kv rows ±30 s around the event
- SHAP contribution bars (from shap_values JSON)
- Human Review form: Confirmed / False Alarm / Maintenance / Unknown + Notes
- Audit trail for this alarm

### `/ai/` AI Risk Center
- Current assessment dial (0–100) + level badge + confidence + alarm status
- "Why?" panel: triggered conditions + SHAP bars
- Risk history line chart (last 24 h, per device)
- Per-device risk comparison bar

### `/analytics/` Historical Analytics
- Date range picker
- KPI cards: total events, alarms, high-risk, critical, false alarm rate, avg risk score
- Charts: alarm frequency (bar), risk distribution (donut), per-device heatmap

### `/map/` Map / Floorplan
- SVG floorplan image background
- Device dots: color = risk level (green/yellow/orange/red)
- Click dot → device detail side-panel

### `/data/` Data Export
- Format: CSV / JSON / AI Training Dataset (with human_label column)
- Range, device, sensor key checkboxes
- Export runs as Celery task → download link when ready

### `/admin-panel/sensors/` Sensor Config
- Table of all SensorParameter rows
- Inline edit: display name, unit, viz type, danger condition, include in AI, active toggle

### `/admin-panel/ai-model/` AI Model Management
- Current model card: version, samples, features, trained_at
- Version history table + Rollback button
- Retrain button → Celery task → progress indicator

### `/admin-panel/users/` + `/admin-panel/organizations/`
- Org tree view
- User table with role selector
- Invite user form

---

## Implementation Phases

### Phase 0 — Scaffold ← START HERE
- [ ] Create `joinik` PostgreSQL database locally
- [ ] `pip install` all dependencies (Django, DRF, channels, celery, redis, psycopg2, scikit-learn, shap, chart.js via CDN)
- [ ] `django-admin startproject config web/`
- [ ] Create all 8 apps
- [ ] `settings.py`: two DB connections — `default` (joinik local) + `thingsboard` (remote read-only)
- [ ] `.env` file with all secrets
- [ ] Redis install check + Celery config
- [ ] Django Channels ASGI setup
- [ ] Base dark theme CSS (Inter font, sidebar, topbar)
- [ ] Login / logout pages

### Phase 1 — Data Layer
- [ ] `apps/core/tb_reader.py` — raw SQL helpers over ThingsBoard DB
- [ ] `apps/core/tb_api.py` — ThingsBoard REST API wrapper (login + device CRUD)
- [ ] `SensorParameter` model + auto-registration migration
- [ ] Seed SensorParameter rows from known keys
- [ ] `Device` model
- [ ] Management command: sync devices from ThingsBoard DB

### Phase 2 — Dashboard + Devices
- [ ] Dashboard view + template (stat cards, live status, recent events)
- [ ] Device List page + Add Device modal (TB provisioning)
- [ ] Device Detail page (dynamic sensor grid)
- [ ] Online/offline detection from `attribute_kv`

### Phase 3 — Live Telemetry
- [ ] Django Channels WebSocket consumer
- [ ] Frontend WebSocket client (live.js)
- [ ] Chart.js integration + auto-viz per SensorParameter (charts.js)
- [ ] Time range selector

### Phase 4 — AI Engine
- [ ] Feature extractor
- [ ] Train initial Random Forest on synthetic dataset
- [ ] SHAP TreeExplainer integration
- [ ] `RiskAssessment` + `AIModelVersion` models
- [ ] Celery scoring task (triggered per new telemetry batch)
- [ ] AI Risk Center page

### Phase 5 — Alarms
- [ ] Alarm creation from RiskAssessment (threshold crossing)
- [ ] Alarm Center page
- [ ] Incident Report page + Human Review form
- [ ] `HumanVerification` model → training data accumulation
- [ ] Email notification on CRITICAL

### Phase 6 — Analytics + Export
- [ ] Historical Analytics page (Chart.js)
- [ ] Event Timeline page (clustered view)
- [ ] Data Export (Celery task → CSV/JSON/training set)

### Phase 7 — Administration
- [ ] Sensor Config page (inline edit)
- [ ] AI Model Management (version list, retrain, rollback)
- [ ] User + Org management
- [ ] Audit Log page
- [ ] Notification config

### Phase 8 — Polish + Deploy
- [ ] SVG Floorplan map view
- [ ] Event Replay
- [ ] Responsive design
- [ ] Move to Proxmox VM (update DB host in .env only)
- [ ] Production settings (DEBUG=False, whitenoise, gunicorn)
