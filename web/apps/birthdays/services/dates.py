"""Date and schedule helpers for birthday reports."""

from datetime import datetime, time, timedelta

from django.utils import timezone


SCHEDULED_SEND_TIME = time(hour=2, minute=0)


def get_local_now(value=None):
    """Return an aware datetime converted to Django's configured timezone."""
    if value is None:
        return timezone.localtime(timezone.now())

    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())

    return timezone.localtime(value)


def calculate_week_period(reference_date, week_starts_on):
    """Return the weekly period containing reference_date for a configured start."""
    days_since_start = (reference_date.weekday() - week_starts_on) % 7
    period_start = reference_date - timedelta(days=days_since_start)
    return period_start, period_start + timedelta(days=6)


def scheduled_datetime_for_period(period_start, week_starts_on, send_day):
    """Return the fixed 02:00 scheduled datetime for a weekly period."""
    scheduled_offset = (send_day - week_starts_on) % 7
    scheduled_date = period_start + timedelta(days=scheduled_offset)
    scheduled_naive = datetime.combine(scheduled_date, SCHEDULED_SEND_TIME)
    return timezone.make_aware(scheduled_naive, timezone.get_current_timezone())


def get_current_period_and_schedule(settings_obj, now=None):
    """Return current period and scheduled datetime for a settings object."""
    local_now = get_local_now(now)
    period_start, period_end = calculate_week_period(
        local_now.date(),
        settings_obj.week_starts_on,
    )
    scheduled_at = scheduled_datetime_for_period(
        period_start,
        settings_obj.week_starts_on,
        settings_obj.send_day,
    )
    return period_start, period_end, scheduled_at, local_now


def is_scheduled_report_due(settings_obj, now=None):
    """Return whether the current weekly report is due for automatic processing."""
    period_start, period_end, scheduled_at, local_now = get_current_period_and_schedule(
        settings_obj,
        now=now,
    )
    return local_now >= scheduled_at, period_start, period_end, scheduled_at, local_now
