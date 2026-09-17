from django.db import models

class SystemSettings(models.Model):
    weather_location = models.CharField(max_length=100, default="New York", help_text="City name for the weather widget")
    
    class Meta:
        verbose_name_plural = "System Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SystemSettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
