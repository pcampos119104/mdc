"""Tests for birthday report services."""

from datetime import date

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.birthdays.models import BirthdayReport, BirthdayReportSettings
from apps.birthdays.services import reports as report_services
from apps.members.models import Member


def _settings(**overrides):
    """Create birthday report settings for service tests."""
    defaults = {
        "is_enabled": True,
        "week_starts_on": 0,
        "send_day": 0,
        "recipients": ["leader@example.com"],
    }
    defaults.update(overrides)
    return BirthdayReportSettings.objects.create(**defaults)


def _patch_successful_generation_and_email(monkeypatch):
    """Patch image generation and e-mail sending to succeed."""
    captured = {}
    monkeypatch.setattr(
        report_services,
        "generate_birthday_report_image",
        lambda members, period_start, period_end: b"jpeg-content",
    )

    def successful_send(report, *, image_content=None):
        """Record generated content sent without reopening the stored image."""
        captured["image_content"] = image_content
        return timezone.now()

    monkeypatch.setattr(
        report_services,
        "send_birthday_report_email",
        successful_send,
    )
    return captured


@pytest.mark.django_db
def test_create_birthday_report_stores_image_and_marks_email_sent(monkeypatch, settings, tmp_path):
    """Report service should store the image before marking the e-mail as sent."""
    settings.MEDIA_ROOT = tmp_path
    settings_obj = _settings()
    Member.objects.create(name="Maria Silva", birth_date=date(1990, 7, 22))
    captured = _patch_successful_generation_and_email(monkeypatch)

    result = report_services.create_birthday_report(
        settings_obj,
        date(2026, 7, 20),
        date(2026, 7, 26),
        is_automatic=True,
    )

    report = result.report
    assert report.send_status == BirthdayReport.SendStatus.SENT
    assert report.member_count == 1
    assert report.recipients == ["leader@example.com"]
    assert report.email_subject == "Aniversariantes da semana - 20/07/2026 a 26/07/2026"
    assert report.image
    assert report.image.storage.exists(report.image.name)
    assert result.image_created is True
    assert result.email_sent is True
    assert captured["image_content"] == b"jpeg-content"


@pytest.mark.django_db
def test_create_birthday_report_preserves_image_when_smtp_fails(monkeypatch, settings, tmp_path):
    """SMTP failures should not remove the generated image or report row."""
    settings.MEDIA_ROOT = tmp_path
    settings.EMAIL_HOST_PASSWORD = "secret-token"
    settings_obj = _settings()
    Member.objects.create(name="Maria Silva", birth_date=date(1990, 7, 22))
    monkeypatch.setattr(
        report_services,
        "generate_birthday_report_image",
        lambda members, period_start, period_end: b"jpeg-content",
    )

    def failing_send(report, *, image_content=None):
        """Raise an SMTP-like failure for tests."""
        raise RuntimeError("SMTP failed with secret-token")

    monkeypatch.setattr(report_services, "send_birthday_report_email", failing_send)

    result = report_services.create_birthday_report(
        settings_obj,
        date(2026, 7, 20),
        date(2026, 7, 26),
        is_automatic=True,
    )

    report = result.report
    assert report.send_status == BirthdayReport.SendStatus.FAILED
    assert report.image.storage.exists(report.image.name)
    assert "secret-token" not in report.error_message
    assert "RuntimeError" in report.error_message
    assert result.email_failed is True


@pytest.mark.django_db
def test_create_birthday_report_records_generation_failure_without_sending(monkeypatch):
    """Image generation failures should keep a report row and skip e-mail sending."""
    settings_obj = _settings()
    Member.objects.create(name="Maria Silva", birth_date=date(1990, 7, 22))

    def failing_generation(members, period_start, period_end):
        """Raise a rendering failure for tests."""
        raise RuntimeError("Chromium failed")

    def unexpected_send(report, *, image_content=None):
        """Fail if e-mail sending is attempted after generation failure."""
        raise AssertionError("E-mail should not be sent")

    monkeypatch.setattr(report_services, "generate_birthday_report_image", failing_generation)
    monkeypatch.setattr(report_services, "send_birthday_report_email", unexpected_send)

    result = report_services.create_birthday_report(
        settings_obj,
        date(2026, 7, 20),
        date(2026, 7, 26),
        is_automatic=True,
    )

    report = result.report
    assert report.send_status == BirthdayReport.SendStatus.FAILED
    assert not report.image
    assert "Chromium failed" in report.error_message
    assert result.generation_failed is True


@pytest.mark.django_db
def test_create_birthday_report_handles_period_without_birthdays(monkeypatch):
    """Periods without birthdays should be recorded without image or e-mail."""
    settings_obj = _settings()
    monkeypatch.setattr(
        report_services,
        "generate_birthday_report_image",
        lambda members, period_start, period_end: pytest.fail("Image should not be generated"),
    )

    result = report_services.create_birthday_report(
        settings_obj,
        date(2026, 7, 20),
        date(2026, 7, 26),
        is_automatic=True,
    )

    report = result.report
    assert report.send_status == BirthdayReport.SendStatus.NO_BIRTHDAYS
    assert report.member_count == 0
    assert not report.image
    assert result.no_birthdays is True


@pytest.mark.django_db
def test_automatic_report_processing_skips_duplicate_period(monkeypatch):
    """Automatic processing should not create another report for the same period."""
    settings_obj = _settings()
    BirthdayReport.objects.create(
        period_start=date(2026, 7, 20),
        period_end=date(2026, 7, 26),
        is_automatic=True,
    )
    _patch_successful_generation_and_email(monkeypatch)

    result = report_services.create_birthday_report(
        settings_obj,
        date(2026, 7, 20),
        date(2026, 7, 26),
        is_automatic=True,
    )

    assert result.skipped is True
    assert BirthdayReport.objects.count() == 1


@pytest.mark.django_db
def test_manual_report_can_reprocess_existing_automatic_period(monkeypatch):
    """Manual generation should create a new row for an already processed period."""
    settings_obj = _settings()
    Member.objects.create(name="Maria Silva", birth_date=date(1990, 7, 22))
    BirthdayReport.objects.create(
        period_start=date(2026, 7, 20),
        period_end=date(2026, 7, 26),
        is_automatic=True,
    )
    _patch_successful_generation_and_email(monkeypatch)

    result = report_services.create_birthday_report(
        settings_obj,
        date(2026, 7, 20),
        date(2026, 7, 26),
        is_automatic=False,
    )

    assert result.report.pk is not None
    assert BirthdayReport.objects.count() == 2


@pytest.mark.django_db
def test_resend_birthday_report_uses_existing_image_and_stored_recipients(monkeypatch, settings, tmp_path):
    """Re-send should use the saved image and the report's stored recipients."""
    settings.MEDIA_ROOT = tmp_path
    report = BirthdayReport.objects.create(
        period_start=date(2026, 7, 20),
        period_end=date(2026, 7, 26),
        recipients=["old@example.com"],
        email_subject="Assunto preservado",
    )
    report.image.save(report.image_filename, ContentFile(b"jpeg-content"), save=True)
    captured = {}

    def fake_send(report_to_send, *, image_content=None):
        """Capture recipients used by re-send."""
        captured["recipients"] = list(report_to_send.recipients)
        captured["image_name"] = report_to_send.image.name
        captured["image_content"] = image_content
        return timezone.now()

    monkeypatch.setattr(report_services, "send_birthday_report_email", fake_send)

    result = report_services.resend_birthday_report(report)

    report.refresh_from_db()
    assert captured["recipients"] == ["old@example.com"]
    assert captured["image_name"] == report.image.name
    assert captured["image_content"] is None
    assert report.send_status == BirthdayReport.SendStatus.SENT
    assert result.email_sent is True
