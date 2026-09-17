import requests
from django.core.cache import cache

def get_current_weather(location=None):
    if not location:
        return None
        
    cache_key = f"weather_data_{location.replace(' ', '_')}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
        
    try:
        url = f"https://wttr.in/{location}?format=j1"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            cc = data.get('current_condition', [{}])[0]
            weather_info = {
                'location': location,
                'temp_C': cc.get('temp_C', '--'),
                'desc': cc.get('weatherDesc', [{}])[0].get('value', ''),
                'humidity': cc.get('humidity', '--')
            }
            cache.set(cache_key, weather_info, timeout=1800) # cache for 30 minutes
            return weather_info
    except Exception:
        pass
        
    return {
        'location': location,
        'temp_C': '--',
        'desc': 'Unavailable',
        'humidity': '--'
    }
