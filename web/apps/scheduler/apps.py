from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class SchedulerConfig(AppConfig):
    name = 'apps.scheduler'
    verbose_name = 'Background Scheduler'

    def ready(self):
        """
        Called once when Django starts. Starts the APScheduler background thread.
        Guard against double-start: Django's reloader spawns two processes.
        RUN_MAIN='true' is set only in the child (worker) process — that's where
        we want the scheduler. In production (no reloader), we always start.
        """
        import os
        run_main = os.environ.get('RUN_MAIN')
        # In dev with reloader: only start in the worker process (RUN_MAIN=true)
        # In production (gunicorn/daphne): RUN_MAIN is not set, always start
        if run_main == 'false':
            return  # Skip in the reloader's monitor process only

        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.executors.pool import ThreadPoolExecutor
        from django.conf import settings

        if getattr(settings, '_APSCHEDULER_RUNNING', False):
            return  # Already started (safety net)
        settings._APSCHEDULER_RUNNING = True

        scheduler = BackgroundScheduler(
            executors={'default': ThreadPoolExecutor(max_workers=2)},
            timezone='Asia/Dhaka',
        )

        # --- Job 1: Sync devices from ThingsBoard every 30 seconds ---
        scheduler.add_job(
            _sync_devices_job,
            trigger='interval',
            seconds=30,
            id='sync_devices',
            replace_existing=True,
            misfire_grace_time=10,
        )

        # --- Job 1.5: Sync Weather every 15 minutes (900 seconds) ---
        def _sync_weather_job():
            from apps.ai_engine.weather import sync_weather_for_all_devices
            try:
                sync_weather_for_all_devices()
            except Exception as e:
                logger.error(f"[weather] Error syncing weather: {e}")

        scheduler.add_job(
            _sync_weather_job,
            trigger='interval',
            minutes=15,
            id='sync_weather',
            replace_existing=True,
        )
        # Run it once immediately on startup
        try:
            _sync_weather_job()
        except Exception:
            pass

        # Run the AI / Telemetry Polling Loop VERY fast (1 second) for real-time live data
        scheduler.add_job(
            _process_telemetry_job,
            'interval',
            seconds=1,
            id='process_telemetry_and_risk_job',
            max_instances=1,
            replace_existing=True
        )
        logger.info("Added job '_process_telemetry_job'.")

        def _escalate_alarms_job():
            from apps.alarms.tasks import escalate_dead_hand_alarms
            escalate_dead_hand_alarms()

        scheduler.add_job(
            _escalate_alarms_job,
            trigger='interval',
            seconds=1,
            id="_escalate_alarms_job",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job '_escalate_alarms_job'.")

        scheduler.start()
        logger.info('[scheduler] APScheduler started: sync=30s, telemetry=5s')


def _sync_devices_job():
    """Sync devices from ThingsBoard to Django DB."""
    try:
        from apps.devices.sync import sync_devices_from_thingsboard
        result = sync_devices_from_thingsboard()
        if any(result.values()):
            import logging
            logging.getLogger(__name__).info(
                f"[sync] added={result['added']} renamed={result['updated']} deleted={result['deleted']}"
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[sync] Error: {e}", exc_info=True)


def _process_telemetry_job():
    """Fetch latest telemetry, run AI scoring, push via WebSockets."""
    try:
        from apps.ai_engine.tasks import process_telemetry_and_risk
        process_telemetry_and_risk()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[telemetry] Error: {e}", exc_info=True)
