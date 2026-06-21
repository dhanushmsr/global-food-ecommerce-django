# booking/apps.py
from django.apps import AppConfig

class BookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'booking'  # 🎯 Leave it exactly like this (NO label line)

    def ready(self):
        import booking.signals