from celery import shared_task
from django.utils import timezone
from .models import Alarm
from apps.notifications.models import NotificationLog, EmergencyContact
import logging

logger = logging.getLogger(__name__)

@shared_task
def escalate_dead_hand_alarms():
    """
    Finds PENDING alarms where the cancellation deadline has passed and
    escalates them, triggering emergency notifications.
    """
    now = timezone.now()
    expired_alarms = Alarm.objects.filter(status='PENDING', cancellation_deadline__lt=now)
    
    for alarm in expired_alarms:
        # 1. Transition state
        alarm.status = 'ESCALATING'
        alarm.save(update_fields=['status'])
        logger.warning(f"Alarm {alarm.id} deadline expired. Escalating to emergency contacts!")
        
        # 2. Trigger notifications (Mocking the dispatch)
        contacts = EmergencyContact.objects.filter(is_active=True).order_by('priority')
        for contact in contacts:
            # Create a pending log
            log = NotificationLog.objects.create(
                alarm=alarm,
                contact=contact,
                status='SENT',
                sent_at=now
            )
            # Mock sending email/SMS
            print(f"[EMERGENCY DISPATCH] Sent {contact.channel} to {contact.target_address} for Alarm {alarm.id}")
            
            # Since this is a mock MVP, mark it delivered instantly
            log.status = 'DELIVERED'
            log.save(update_fields=['status'])
            
        # 3. Mark as notified
        alarm.status = 'EMERGENCY_NOTIFIED'
        alarm.save(update_fields=['status'])
