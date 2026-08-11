"""Tests for birthday report e-mail delivery."""

from datetime import date
from types import SimpleNamespace

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
def test_send_birthday_report_email_downloads_stored_s3_image_with_get_object(
    monkeypatch,
    settings,
):
    """Re-sends should attach S3 images without opening the Django field file."""
    class SourceFile:
        """S3 response body that records closure."""

        def __init__(self):
            """Initialize the response body state."""
            self.closed = False

        def read(self):
            """Return the downloaded report bytes."""
            return b"stored-jpeg-content"

        def close(self):
            """Record that the response body was closed."""
            self.closed = True

    class S3Client:
        """S3 client double that records object downloads."""

        def __init__(self, source_file):
            """Configure the response body returned by GetObject."""
            self.source_file = source_file
            self.calls = []

        def get_object(self, **kwargs):
            """Return a GetObject-like response."""
            self.calls.append(kwargs)
            return {"Body": self.source_file}

    class DirectS3Storage(S3Storage):
        """S3 storage double that needs no network configuration."""

        def _normalize_name(self, name):
            """Return the expected media-prefixed object key."""
            return f"media/{name}"

        @property
        def connection(self):
            """Return the configured S3 client double."""
            return self._connection

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    source_file = SourceFile()
    client = S3Client(source_file)
    storage = object.__new__(DirectS3Storage)
    storage.bucket_name = "mdc-media"
    storage._connection = SimpleNamespace(meta=SimpleNamespace(client=client))
    monkeypatch.setattr(BirthdayReport._meta.get_field("image"), "storage", storage)
    report = BirthdayReport.objects.create(
        period_start=date(2026, 7, 20),
        period_end=date(2026, 7, 26),
        recipients=["leader@example.com"],
    )
    report.image.name = "birthday_reports/2026/07/aniversariantes.jpg"
    def unexpected_open(mode):
        """Fail if re-send attempts a HeadObject-backed storage read."""
        raise AssertionError("S3 re-send should use the presigned URL")

    monkeypatch.setattr(report.image, "open", unexpected_open)

    emails.send_birthday_report_email(report)

    assert client.calls == [
        {
            "Bucket": "mdc-media",
            "Key": f"media/{report.image.name}",
        }
    ]
    assert source_file.closed is True
    _filename, content, _mimetype = mail.outbox[0].attachments[0]
    assert content == b"stored-jpeg-content"
