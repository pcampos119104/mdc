"""App configuration for the members app."""

from django.apps import AppConfig


class MembersConfig(AppConfig):
    """Configure the members application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.members"
