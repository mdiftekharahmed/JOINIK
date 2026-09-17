from django.db import models

class SensorParameter(models.Model):
    VIZ_CHOICES = [
        ('AUTO', 'Auto-detect'),
        ('GAUGE', 'Gauge (0-100 or min/max)'),
        ('GRAPH_3AXIS', '3-Axis Graph (x/y/z)'),
        ('GRAPH', 'Line Graph'),
        ('STATUS', 'Status Indicator (ON/OFF)'),
        ('BATTERY', 'Battery Level'),
        ('BAR', 'Bar Meter'),
    ]
    DATA_TYPES = [
        ('BOOLEAN', 'Boolean'),
        ('NUMERIC', 'Numeric'),
        ('STRING', 'String'),
    ]

    key = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default='NUMERIC')
    unit = models.CharField(max_length=20, blank=True)
    visualization = models.CharField(max_length=20, choices=VIZ_CHOICES, default='AUTO')
    danger_condition = models.CharField(max_length=255, blank=True, help_text="e.g. 'value > 2.0'")
    include_in_ai = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name
