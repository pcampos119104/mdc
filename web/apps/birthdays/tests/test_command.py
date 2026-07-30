"""Tests for the scheduled birthday report management command."""

from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.birthdays.models import BirthdayReport, BirthdayReportSettings
from apps.birthdays.services.dates import calculate_week_period
from apps.birthdays.services import reports as report_services
from apps.members.models import Member


def _configure_due_settings(**overrides):
    """Create settings that are due for the current local date."""
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    defaults = {
        "is_enabled": True,
        "week_starts_on": yesterday.weekday(),
        "send_day": yesterday.weekday(),
        "recipients": ["leader@example.com"],
    }
    defaults.update(overrides)
    return BirthdayReportSettings.objects.create(**defaults)


def _patch_generation_success(monkeypatch):
    """Patch command dependencies so image generation succeeds."""
    monkeypatch.setattr(
        report_services,
        "generate_birthday_report_image",
        lambda members, period_start, period_end: b"jpeg-content",
    )


@pytest.mark.django_db
def test_process_scheduled_birthday_skips_when_feature_disabled():
    """Command should log a skipped execution when the feature is disabled."""
    BirthdayReportSettings.get_solo()
    stdout = StringIO()

    call_command("process_scheduled_birthday", stdout=stdout)

    assert "Execução ignorada" in stdout.getvalue()
    assert "Funcionalidade desativada" in stdout.getvalue()


@pytest.mark.django_db
def test_process_scheduled_birthday_skips_before_scheduled_day_or_time():
    """Command should skip when the current period is not due yet."""
    tomorrow = timezone.localdate() + timedelta(days=1)
    _configure_due_settings(send_day=tomorrow.weekday())
    stdout = StringIO()

    call_command("process_scheduled_birthday", stdout=stdout)

    assert "Execução ignorada" in stdout.getvalue()
    assert "Ainda não chegou" in stdout.getvalue()


@pytest.mark.django_db
def test_process_scheduled_birthday_skips_existing_automatic_report(monkeypatch):
    """Command should not create a duplicate automatic report for the period."""
    settings_obj = _configure_due_settings()
    period_start, period_end = calculate_week_period(
        timezone.localdate(),
        settings_obj.week_starts_on,
    )
    BirthdayReport.objects.create(
        period_start=period_start,
        period_end=period_end,
        is_automatic=True,
    )
    _patch_generation_success(monkeypatch)
    stdout = StringIO()

    call_command("process_scheduled_birthday", stdout=stdout)

    assert "Execução ignorada" in stdout.getvalue()
    assert "já foi processado" in stdout.getvalue()
    assert BirthdayReport.objects.count() == 1


@pytest.mark.django_db
def test_process_scheduled_birthday_sends_due_report(monkeypatch, settings, tmp_path):
    """Command should create a report and send e-mail when due."""
    settings.MEDIA_ROOT = tmp_path
    _configure_due_settings()
    today = timezone.localdate()
    Member.objects.create(name="Maria Silva", birth_date=date(1990, today.month, today.day))
    _patch_generation_success(monkeypatch)
    monkeypatch.setattr(
        report_services,
        "send_birthday_report_email",
        lambda report: timezone.now(),
    )
    stdout = StringIO()

    call_command("process_scheduled_birthday", stdout=stdout)

    report = BirthdayReport.objects.get()
    assert "Relatório criado" in stdout.getvalue()
    assert "E-mail enviado" in stdout.getvalue()
    assert report.send_status == BirthdayReport.SendStatus.SENT
    assert report.is_automatic is True


@pytest.mark.django_db
def test_process_scheduled_birthday_logs_email_failure(monkeypatch, settings, tmp_path):
    """Command should keep report and log failure when e-mail sending fails."""
    settings.MEDIA_ROOT = tmp_path
    _configure_due_settings()
    today = timezone.localdate()
    Member.objects.create(name="Maria Silva", birth_date=date(1990, today.month, today.day))
    _patch_generation_success(monkeypatch)

    def failing_send(report):
        """Raise an e-mail failure for command tests."""
        raise RuntimeError("SMTP indisponível")

    monkeypatch.setattr(report_services, "send_birthday_report_email", failing_send)
    stdout = StringIO()
    stderr = StringIO()

    call_command("process_scheduled_birthday", stdout=stdout, stderr=stderr)

    report = BirthdayReport.objects.get()
    assert "Relatório criado" in stdout.getvalue()
    assert "Falha no envio" in stderr.getvalue()
    assert report.send_status == BirthdayReport.SendStatus.FAILED
    assert report.image
