import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.devices.models import Device
from apps.core.tb_reader import get_all_devices
import uuid

tb_devices = get_all_devices()
for td in tb_devices:
    Device.objects.get_or_create(
        tb_device_id=td['id'],
        defaults={'name': td['name']}
    )

print(f"Synced {len(tb_devices)} devices.")
