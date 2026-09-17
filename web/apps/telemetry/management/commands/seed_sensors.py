from django.core.management.base import BaseCommand
from apps.telemetry.models import SensorParameter

class Command(BaseCommand):
    help = 'Seeds initial sensor parameters from known keys'

    def handle(self, *args, **kwargs):
        initial_keys = [
            {'key': 'accel_x', 'display_name': 'Acceleration X', 'data_type': 'NUMERIC', 'unit': 'g', 'visualization': 'GRAPH_3AXIS'},
            {'key': 'accel_y', 'display_name': 'Acceleration Y', 'data_type': 'NUMERIC', 'unit': 'g', 'visualization': 'GRAPH_3AXIS'},
            {'key': 'accel_z', 'display_name': 'Acceleration Z', 'data_type': 'NUMERIC', 'unit': 'g', 'visualization': 'GRAPH_3AXIS'},
            {'key': 'gyro_x', 'display_name': 'Gyroscope X', 'data_type': 'NUMERIC', 'unit': 'dps', 'visualization': 'GRAPH_3AXIS'},
            {'key': 'gyro_y', 'display_name': 'Gyroscope Y', 'data_type': 'NUMERIC', 'unit': 'dps', 'visualization': 'GRAPH_3AXIS'},
            {'key': 'gyro_z', 'display_name': 'Gyroscope Z', 'data_type': 'NUMERIC', 'unit': 'dps', 'visualization': 'GRAPH_3AXIS'},
            {'key': 'motion', 'display_name': 'Motion Detected', 'data_type': 'BOOLEAN', 'visualization': 'STATUS'},
            {'key': 'vibration_intensity', 'display_name': 'Vibration Intensity', 'data_type': 'NUMERIC', 'visualization': 'BAR'},
            {'key': 'humidity', 'display_name': 'Humidity', 'data_type': 'NUMERIC', 'unit': '%', 'visualization': 'GAUGE'},
            {'key': 'temperature', 'display_name': 'Temperature', 'data_type': 'NUMERIC', 'unit': 'C', 'visualization': 'GAUGE'},
            {'key': 'power_cut', 'display_name': 'Power Cut', 'data_type': 'BOOLEAN', 'visualization': 'STATUS'},
            {'key': 'cctv_cut', 'display_name': 'CCTV Cut', 'data_type': 'BOOLEAN', 'visualization': 'STATUS'},
        ]

        count = 0
        for item in initial_keys:
            obj, created = SensorParameter.objects.get_or_create(
                key=item['key'],
                defaults=item
            )
            if created:
                count += 1
                
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {count} sensor parameters.'))
