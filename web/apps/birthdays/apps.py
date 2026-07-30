"""App configuration for birthday reports."""

from django.apps import AppConfig


class BirthdaysConfig(AppConfig):
    """Configure the birthdays application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.birthdays"
