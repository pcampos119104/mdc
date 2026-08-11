"""Tests for birthday report e-mail delivery."""

from datetime import date

import pytest
from django.core import mail
from storages.backends.s3 import S3Storage

from apps.birthdays.models import BirthdayReport
from apps.birthdays.services import emails


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

    sent_at = emails.send_birthday_report_email(report, image_content=image_content)

    assert sent_at is not None
    assert len(mail.outbox) == 1
    filename, content, mimetype = mail.outbox[0].attachments[0]
    assert filename == report.image_filename
    assert content == image_content
    assert mimetype == "image/jpeg"


@pytest.mark.django_db
def test_send_birthday_report_email_downloads_stored_s3_image_with_presigned_get(
    monkeypatch,
    settings,
):
    """Re-sends should attach S3 images without opening the Django field file."""
    class PresignedS3Storage(S3Storage):
        """S3 storage double that provides a deterministic signed URL."""

        def url(self, name, parameters=None, expire=None, http_method=None):
            """Return a signed URL without creating an S3 connection."""
            return f"https://s3.example.com/{name}?signature=example"

    class Response:
        """HTTP response double for a presigned image GET."""

        def __enter__(self):
            """Return the open response body."""
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            """Close the response context."""

        def read(self):
            """Return the downloaded report bytes."""
            return b"stored-jpeg-content"

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    storage = object.__new__(PresignedS3Storage)
    monkeypatch.setattr(BirthdayReport._meta.get_field("image"), "storage", storage)
    report = BirthdayReport.objects.create(
        period_start=date(2026, 7, 20),
        period_end=date(2026, 7, 26),
        recipients=["leader@example.com"],
    )
    report.image.name = "birthday_reports/2026/07/aniversariantes.jpg"
    captured = {}

    def fake_urlopen(url, *, timeout):
        """Capture the signed URL used to download the attachment."""
        captured["url"] = url
        captured["timeout"] = timeout
        return Response()

    def unexpected_open(mode):
        """Fail if re-send attempts a HeadObject-backed storage read."""
        raise AssertionError("S3 re-send should use the presigned URL")

    monkeypatch.setattr(emails, "urlopen", fake_urlopen)
    monkeypatch.setattr(report.image, "open", unexpected_open)

    emails.send_birthday_report_email(report)

    assert captured == {
        "url": f"https://s3.example.com/{report.image.name}?signature=example",
        "timeout": emails.REPORT_IMAGE_DOWNLOAD_TIMEOUT,
    }
    _filename, content, _mimetype = mail.outbox[0].attachments[0]
    assert content == b"stored-jpeg-content"
