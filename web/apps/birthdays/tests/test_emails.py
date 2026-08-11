"""Tests for birthday report e-mail delivery."""

from datetime import date

import pytest
from django.core import mail

from apps.birthdays.models import BirthdayReport
from apps.birthdays.services.emails import send_birthday_report_email


@pytest.mark.django_db
def test_send_birthday_report_email_uses_supplied_image_content(monkeypatch, settings):
    """New reports should be e-mailed without reopening their stored image."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    report = BirthdayReport.objects.create(
        period_start=date(2026, 7, 20),
        period_end=date(2026, 7, 26),
        recipients=["leader@example.com"],
    )
    report.image.name = "birthday_reports/2026/07/aniversariantes.jpg"
    image_content = b"jpeg-content"

    def unexpected_open(mode):
        """Fail if delivery tries to read the image from storage."""
        raise AssertionError("The supplied image content should be used")

    monkeypatch.setattr(report.image, "open", unexpected_open)

    sent_at = send_birthday_report_email(report, image_content=image_content)

    assert sent_at is not None
    assert len(mail.outbox) == 1
    filename, content, mimetype = mail.outbox[0].attachments[0]
    assert filename == report.image_filename
    assert content == image_content
    assert mimetype == "image/jpeg"
