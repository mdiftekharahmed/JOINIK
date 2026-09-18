import requests
import logging
from django.core.cache import cache
from apps.devices.models import Device

logger = logging.getLogger(__name__)

def fetch_weather_for_location(lat, lon):
    """
    Fetches current weather from Open-Meteo for a given lat/lon.
    Returns a dictionary of weather parameters.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["temperature_2m", "precipitation", "rain", "weather_code", "wind_speed_10m", "wind_gusts_10m"]
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})
        
        weather_code = current.get("weather_code", 0)
        wind_speed = current.get("wind_speed_10m", 0)
        wind_gusts = current.get("wind_gusts_10m", 0)
        precipitation = current.get("precipitation", 0)
        
        # Determine storm/environmental disturbance flag
        # Open-Meteo WMO Codes:
        # 50-69: Drizzle/Rain
        # 70-79: Snow
        # 80-82: Rain showers
        # 95-99: Thunderstorm
        storm_flag = weather_code >= 95 or wind_speed > 30 or wind_gusts > 50 or precipitation > 10
        
        return {
            "temperature": current.get("temperature_2m", 0),
            "precipitation": precipitation,
            "rain": current.get("rain", 0),
            "weather_code": weather_code,
            "wind_speed": wind_speed,
            "wind_gusts": wind_gusts,
            "storm_flag": storm_flag,
            "weather_state": "Stormy" if storm_flag else "Normal"
        }
    except Exception as e:
        logger.error(f"Failed to fetch weather from Open-Meteo for ({lat}, {lon}): {e}")
        return None

def get_cached_weather(device_id):
    """
    Returns the cached weather data for a specific device.
    """
    cache_key = f"weather_device_{device_id}"
    return cache.get(cache_key)

def sync_weather_for_all_devices():
    """
    Scheduled job to fetch weather for all unique locations.
    """
    devices = Device.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    
    # Group by unique lat/lon rounded to 2 decimal places to avoid redundant API calls
    location_groups = {}
    for device in devices:
        loc_key = (round(device.latitude, 2), round(device.longitude, 2))
        if loc_key not in location_groups:
            location_groups[loc_key] = []
        location_groups[loc_key].append(device.id)
        
    for (lat, lon), device_ids in location_groups.items():
        weather_data = fetch_weather_for_location(lat, lon)
        if weather_data:
            for d_id in device_ids:
                cache.set(f"weather_device_{d_id}", weather_data, timeout=1200) # Cache for 20 mins
