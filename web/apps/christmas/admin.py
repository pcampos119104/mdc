"""Admin configuration for the Natal Feliz campaign."""

from django.contrib import admin

from .models import Child


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    """Admin interface for children participating in Natal Feliz."""

    list_display = ("name", "mother_name", "birth_date")
    search_fields = ("name", "mother_name")
