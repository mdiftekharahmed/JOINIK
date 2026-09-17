"""
ThingsBoard direct-SQL reader.
Uses raw psycopg2 over the 'thingsboard' DB connection defined in settings.
All queries are read-only.
"""
import logging
from datetime import datetime, timezone
from django.db import connections

logger = logging.getLogger(__name__)

# Sensor keys we care about — mapped to their value column
NUMERIC_KEYS = {
    'accel_x', 'accel_y', 'accel_z',
    'gyro_x', 'gyro_y', 'gyro_z',
    'humidity', 'temperature', 'vibration_intensity',
}
BOOLEAN_KEYS = {'motion', 'cctv_cut', 'power_cut'}
STRING_KEYS = {'device_mac', 'timestamp'}


def _conn():
    return connections['thingsboard']


def get_all_devices():
    """Return list of dicts from TB device table."""
    with _conn().cursor() as cur:
        cur.execute("""
            SELECT
                id::text,
                name,
                type,
                created_time
            FROM device
            ORDER BY created_time DESC
        """)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_device_online(tb_device_id: str) -> bool:
    """Determine online status based on recent data activity."""
    last_activity = get_last_activity(tb_device_id)
    if not last_activity:
        return False
    
    # Consider online if data was received in the last 60 seconds
    delta = (datetime.now(timezone.utc) - last_activity).total_seconds()
    return delta < 60


def get_last_activity(tb_device_id: str):
    """Return last activity datetime (UTC) from attribute_kv key 45."""
    with _conn().cursor() as cur:
        cur.execute("""
            SELECT long_v
            FROM attribute_kv
            WHERE entity_id = %s::uuid
              AND attribute_key = 45
        """, [tb_device_id])
        row = cur.fetchone()
        if row and row[0]:
            return datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc)
        return None


def get_latest_telemetry(tb_device_id: str) -> dict:
    """
    Return the most recent value for every sensor key for this device.
    Uses ts_kv_latest for speed.
    """
    with _conn().cursor() as cur:
        cur.execute("""
            SELECT
                kd.key,
                t.bool_v,
                t.long_v,
                t.dbl_v,
                t.str_v,
                t.ts
            FROM ts_kv_latest t
            JOIN key_dictionary kd ON kd.key_id = t.key
            WHERE t.entity_id = %s::uuid
        """, [tb_device_id])
        result = {}
        for key, bool_v, long_v, dbl_v, str_v, ts in cur.fetchall():
            if dbl_v is not None:
                value = dbl_v
            elif long_v is not None:
                value = long_v
            elif bool_v is not None:
                value = bool_v
            else:
                value = str_v
            result[key] = {
                'value': value,
                'ts': datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else None,
            }
        return result


def get_telemetry_range(tb_device_id: str, start_ms: int, end_ms: int,
                        keys: list = None, limit: int = 5000) -> list:
    """
    Return time-series rows for a device in [start_ms, end_ms].
    Returns list of dicts: {ts, key, value}
    """
    with _conn().cursor() as cur:
        if keys:
            # Convert key names to key_ids
            cur.execute("""
                SELECT key_id FROM key_dictionary WHERE key = ANY(%s)
            """, [keys])
            key_ids = [r[0] for r in cur.fetchall()]
            if not key_ids:
                return []
            cur.execute("""
                SELECT
                    kd.key,
                    t.bool_v, t.long_v, t.dbl_v, t.str_v,
                    t.ts
                FROM ts_kv t
                JOIN key_dictionary kd ON kd.key_id = t.key
                WHERE t.entity_id = %s::uuid
                  AND t.key = ANY(%s)
                  AND t.ts BETWEEN %s AND %s
                ORDER BY t.ts DESC
                LIMIT %s
            """, [tb_device_id, key_ids, start_ms, end_ms, limit])
        else:
            cur.execute("""
                SELECT
                    kd.key,
                    t.bool_v, t.long_v, t.dbl_v, t.str_v,
                    t.ts
                FROM ts_kv t
                JOIN key_dictionary kd ON kd.key_id = t.key
                WHERE t.entity_id = %s::uuid
                  AND t.ts BETWEEN %s AND %s
                ORDER BY t.ts DESC
                LIMIT %s
            """, [tb_device_id, start_ms, end_ms, limit])

        rows = []
        for key, bool_v, long_v, dbl_v, str_v, ts in cur.fetchall():
            if dbl_v is not None:
                value = dbl_v
            elif long_v is not None:
                value = long_v
            elif bool_v is not None:
                value = bool_v
            else:
                value = str_v
            rows.append({
                'key': key,
                'value': value,
                'ts': datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else None,
                'ts_ms': ts,
            })
        return rows


def get_all_telemetry_rows(tb_device_id: str, limit: int = 2000,
                           offset: int = 0) -> tuple:
    """
    Return all telemetry rows for a device, newest first.
    Returns (rows, total_count).
    Each row is a dict with all sensor columns as keys.
    Groups readings by timestamp so each ts produces one flat dict.
    """
    with _conn().cursor() as cur:
        # Count distinct timestamps
        cur.execute("""
            SELECT COUNT(DISTINCT ts)
            FROM ts_kv
            WHERE entity_id = %s::uuid
        """, [tb_device_id])
        total = cur.fetchone()[0]

        # Get distinct timestamps with pagination
        cur.execute("""
            SELECT DISTINCT ts
            FROM ts_kv
            WHERE entity_id = %s::uuid
            ORDER BY ts DESC
            LIMIT %s OFFSET %s
        """, [tb_device_id, limit, offset])
        timestamps = [r[0] for r in cur.fetchall()]

        if not timestamps:
            return [], total

        # Fetch all keys for those timestamps
        cur.execute("""
            SELECT
                t.ts,
                kd.key,
                t.bool_v, t.long_v, t.dbl_v, t.str_v
            FROM ts_kv t
            JOIN key_dictionary kd ON kd.key_id = t.key
            WHERE t.entity_id = %s::uuid
              AND t.ts = ANY(%s)
            ORDER BY t.ts DESC, kd.key
        """, [tb_device_id, timestamps])

        # Pivot: group by ts
        from collections import defaultdict
        grouped = defaultdict(dict)
        for ts, key, bool_v, long_v, dbl_v, str_v in cur.fetchall():
            if dbl_v is not None:
                val = dbl_v
            elif long_v is not None:
                val = long_v
            elif bool_v is not None:
                val = int(bool_v)
            else:
                val = str_v
            grouped[ts][key] = val

        rows = []
        for ts in timestamps:
            row = {'ts': datetime.fromtimestamp(ts / 1000, tz=timezone.utc), 'ts_ms': ts}
            row.update(grouped[ts])
            rows.append(row)

        return rows, total


def get_known_keys(tb_device_id: str) -> list:
    """Return sorted list of telemetry key names seen for this device."""
    with _conn().cursor() as cur:
        cur.execute("""
            SELECT DISTINCT kd.key
            FROM ts_kv t
            JOIN key_dictionary kd ON kd.key_id = t.key
            WHERE t.entity_id = %s::uuid
            ORDER BY kd.key
        """, [tb_device_id])
        return [r[0] for r in cur.fetchall()]


def get_scan_sessions(tb_device_id: str, limit: int = 50, offset: int = 0) -> list:
    """
    Returns distinct scan sessions for a device by grouping telemetry around the 'scan_timestamp' key.
    A scan session represents a single dense burst of data.
    """
    with _conn().cursor() as cur:
        cur.execute("""
            SELECT t.dbl_v as session_id, MIN(t.ts) as start_ts, MAX(t.ts) as end_ts, COUNT(t.ts) as points
            FROM ts_kv t
            JOIN key_dictionary kd ON kd.key_id = t.key
            WHERE t.entity_id = %s::uuid
              AND kd.key = 'scan_timestamp'
            GROUP BY t.dbl_v
            ORDER BY start_ts DESC
            LIMIT %s OFFSET %s
        """, [tb_device_id, limit, offset])
        
        sessions = []
        for session_id, start_ts, end_ts, points in cur.fetchall():
            if session_id:
                start_dt = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc)
                end_dt = datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc)
                duration = (end_dt - start_dt).total_seconds()
                sessions.append({
                    'session_id': session_id,
                    'start_time': start_dt,
                    'end_time': end_dt,
                    'duration_sec': duration,
                    'data_points': points
                })
        return sessions

def get_session_telemetry(tb_device_id: str, session_id: float) -> list:
    """
    Returns all telemetry grouped by timestamp for a specific scan session ID.
    First finds the precise time window of the session, then extracts all telemetry within that window.
    """
    with _conn().cursor() as cur:
        cur.execute("""
            SELECT MIN(t.ts), MAX(t.ts)
            FROM ts_kv t
            JOIN key_dictionary kd ON kd.key_id = t.key
            WHERE t.entity_id = %s::uuid
              AND kd.key = 'scan_timestamp'
              AND t.dbl_v = %s
        """, [tb_device_id, session_id])
        
        row = cur.fetchone()
        if not row or not row[0]:
            return []
            
        start_ts, end_ts = row[0], row[1]
        
        # Add a 1-second buffer on either side
        start_ts -= 1000
        end_ts += 1000
        
        # We can just reuse get_telemetry_range
        rows = get_telemetry_range(tb_device_id, start_ts, end_ts, limit=50000)
        
        # Group by timestamp (ts_ms)
        from collections import defaultdict
        grouped = defaultdict(dict)
        for r in rows:
            grouped[r['ts_ms']][r['key']] = r['value']
            
        final_rows = []
        for ts_ms, data in grouped.items():
            row_dict = {'ts': datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc), 'ts_ms': ts_ms}
            row_dict.update(data)
            final_rows.append(row_dict)
            
        # Sort by timestamp ascending for playback/charts
        final_rows.sort(key=lambda x: x['ts_ms'])
        return final_rows
