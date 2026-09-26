"""App configuration for the Natal Feliz campaign."""

from django.apps import AppConfig


class ChristmasConfig(AppConfig):
    """Configure the Natal Feliz campaign application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.christmas"
    verbose_name = "Natal Feliz"
