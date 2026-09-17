"""
Device synchronization utilities.
Syncs Django Device records to match what's in the ThingsBoard database.
- New TB devices are added to Django.
- Devices deleted from TB are deleted from Django (cascade deletes alarms, assessments, etc).
"""
import logging
from apps.core.tb_reader import get_all_devices

logger = logging.getLogger(__name__)


def sync_devices_from_thingsboard():
    """
    Full bi-directional sync:
    1. Upsert all devices found in ThingsBoard into Django.
    2. Delete Django devices that no longer exist in ThingsBoard.

    Returns a dict with stats: {'added': int, 'updated': int, 'deleted': int}
    """
    # Import here to avoid circular imports at module load time
    from apps.devices.models import Device

    try:
        tb_devices = get_all_devices()
    except Exception as e:
        logger.error(f"[sync] Failed to fetch devices from ThingsBoard: {e}")
        return {'added': 0, 'updated': 0, 'deleted': 0}

    # Build a map of tb_device_id -> name from ThingsBoard
    tb_device_map = {str(td['id']): td['name'] for td in tb_devices}
    tb_ids_set = set(tb_device_map.keys())

    added = 0
    updated = 0

    # Upsert: create or update name
    for tb_id, tb_name in tb_device_map.items():
        obj, created = Device.objects.get_or_create(
            tb_device_id=tb_id,
            defaults={'name': tb_name}
        )
        if created:
            added += 1
            logger.info(f"[sync] Added device: {tb_name} ({tb_id})")
        elif obj.name != tb_name:
            # Device was renamed in ThingsBoard — keep in sync
            obj.name = tb_name
            obj.save(update_fields=['name'])
            updated += 1
            logger.info(f"[sync] Renamed device: {obj.name} -> {tb_name} ({tb_id})")

    # Delete: remove Django devices not in ThingsBoard anymore
    django_ids = set(
        str(uuid_val) for uuid_val in Device.objects.values_list('tb_device_id', flat=True)
    )
    stale_ids = django_ids - tb_ids_set
    deleted = 0
    if stale_ids:
        deleted_qs = Device.objects.filter(tb_device_id__in=stale_ids)
        stale_names = list(deleted_qs.values_list('name', flat=True))
        deleted_count, _ = deleted_qs.delete()
        deleted = deleted_count
        for name in stale_names:
            logger.info(f"[sync] Deleted stale device: {name}")

    return {'added': added, 'updated': updated, 'deleted': deleted}
