"""Admin configuration for birthday reports."""

from django.contrib import admin

from .models import BirthdayReport, BirthdayReportSettings


@admin.register(BirthdayReportSettings)
class BirthdayReportSettingsAdmin(admin.ModelAdmin):
    """Admin interface for the singleton birthday report settings."""

    list_display = ("is_enabled", "week_starts_on", "send_day", "updated_at")

    def has_add_permission(self, request):
        """Allow adding settings only while the singleton row does not exist."""
        return not BirthdayReportSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting the singleton settings row from the admin."""
        return False


@admin.register(BirthdayReport)
class BirthdayReportAdmin(admin.ModelAdmin):
    """Admin interface for generated birthday reports."""

    list_display = (
        "period_start",
        "period_end",
        "member_count",
        "send_status",
        "sent_at",
        "is_automatic",
        "generated_at",
    )
    list_filter = ("send_status", "is_automatic", "generated_at")
    search_fields = ("email_subject", "error_message")
    readonly_fields = ("generated_at", "updated_at")
