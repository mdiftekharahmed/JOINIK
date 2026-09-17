import requests
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

class ThingsBoardAPI:
    def __init__(self):
        self.base_url = settings.TB_URL.rstrip('/')
        self.username = settings.TB_ADMIN_EMAIL
        self.password = settings.TB_ADMIN_PASSWORD
        
    def _get_token(self):
        # Check cache first
        token = cache.get('tb_jwt_token')
        if token:
            return token
            
        # Need to login
        login_url = f"{self.base_url}/api/auth/login"
        payload = {
            "username": self.username,
            "password": self.password
        }
        
        try:
            response = requests.post(login_url, json=payload)
            response.raise_for_status()
            data = response.json()
            token = data.get('token')
            
            # Cache the token (typically valid for 2.5 hours, let's cache for 2 hours)
            cache.set('tb_jwt_token', token, timeout=7200)
            return token
        except Exception as e:
            logger.error(f"Failed to authenticate with ThingsBoard: {e}")
            raise
            
    def _headers(self):
        token = self._get_token()
        return {
            'Content-Type': 'application/json',
            'X-Authorization': f'Bearer {token}'
        }
        
    def create_device(self, name, device_type="default", label=""):
        url = f"{self.base_url}/api/device"
        payload = {
            "name": name,
            "type": device_type,
            "label": label,
        }
        
        response = requests.post(url, json=payload, headers=self._headers())
        response.raise_for_status()
        return response.json()
        
    def get_device_credentials(self, device_id):
        url = f"{self.base_url}/api/device/{device_id}/credentials"
        response = requests.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json()
        
    def delete_device(self, device_id):
        url = f"{self.base_url}/api/device/{device_id}"
        response = requests.delete(url, headers=self._headers())
        response.raise_for_status()
        return True
