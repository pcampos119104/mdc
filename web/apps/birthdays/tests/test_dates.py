"""Tests for birthday report date calculations."""

from datetime import date, time, timezone as datetime_timezone

import pytest
from django.utils import timezone

from apps.birthdays.models import BirthdayReportSettings
from apps.birthdays.services.dates import (
    calculate_week_period,
    is_scheduled_report_due,
    scheduled_datetime_for_period,
)


@pytest.mark.parametrize("week_starts_on", range(7))
def test_calculate_week_period_for_each_week_start(week_starts_on):
    """Weekly period should start on each configured weekday."""
    reference_date = date(2026, 7, 22)

    period_start, period_end = calculate_week_period(reference_date, week_starts_on)

    assert period_start.weekday() == week_starts_on
    assert period_start <= reference_date <= period_end
    assert (period_end - period_start).days == 6


def test_calculate_week_period_crossing_month_boundary():
    """Weekly period calculation should support month boundaries."""
    period_start, period_end = calculate_week_period(date(2026, 8, 1), 4)

    assert period_start == date(2026, 7, 31)
    assert period_end == date(2026, 8, 6)


def test_calculate_week_period_crossing_year_boundary():
    """Weekly period calculation should support year boundaries."""
    period_start, period_end = calculate_week_period(date(2026, 1, 1), 0)

    assert period_start == date(2025, 12, 29)
    assert period_end == date(2026, 1, 4)


def test_scheduled_datetime_uses_configured_timezone():
    """Scheduled datetime should be aware in Django's active timezone."""
    with timezone.override("America/Sao_Paulo"):
        scheduled_at = scheduled_datetime_for_period(
            date(2026, 7, 20),
            week_starts_on=0,
            send_day=2,
        )

    assert scheduled_at.tzinfo is not None
    assert scheduled_at.date() == date(2026, 7, 22)
    assert scheduled_at.time() == time(2, 0)


def test_is_scheduled_report_due_respects_day_and_time():
    """Scheduled processing should wait until the configured day and time."""
    settings_obj = BirthdayReportSettings(
        is_enabled=True,
        week_starts_on=0,
        send_day=2,
        recipients=["leader@example.com"],
    )

    before_due, *_ = is_scheduled_report_due(
        settings_obj,
        now=timezone.datetime(2026, 7, 22, 1, 59, tzinfo=datetime_timezone.utc),
    )
    after_due, *_ = is_scheduled_report_due(
        settings_obj,
        now=timezone.datetime(2026, 7, 22, 2, 0, tzinfo=datetime_timezone.utc),
    )

    assert before_due is False
    assert after_due is True
