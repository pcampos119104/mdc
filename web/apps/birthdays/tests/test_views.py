"""Tests for birthday report views."""

from datetime import date

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from storages.backends.s3 import S3Storage

from apps.birthdays.models import BirthdayReport, BirthdayReportSettings
from apps.birthdays.services.reports import BirthdayReportResult


def _create_user(django_user_model, *, is_staff=False):
    """Create a user for birthday view tests."""
    return django_user_model.objects.create_user(
        username="staff" if is_staff else "member",
        email="staff@example.com" if is_staff else "member@example.com",
        password="secret-pass-123",
        is_staff=is_staff,
    )


def _settings_post_data(**overrides):
    """Return valid settings POST data."""
    data = {
        "is_enabled": "on",
        "week_starts_on": "0",
        "send_day": "0",
        "recipients_text": "leader@example.com",
        "action": "save",
    }
    data.update(overrides)
    return data


def _report_with_image():
    """Create a birthday report with a stored image."""
    report = BirthdayReport.objects.create(
        period_start=date(2026, 7, 20),
        period_end=date(2026, 7, 26),
        recipients=["leader@example.com"],
    )
    report.image.save(report.image_filename, ContentFile(b"jpeg-content"), save=True)
    return report


@pytest.mark.django_db
def test_birthday_settings_requires_staff_access(client, django_user_model):
    """Only staff users should access birthday settings."""
    url = reverse("birthdays:settings")

    anonymous_response = client.get(url)

    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(reverse("account_login"))

    user = _create_user(django_user_model)
    client.force_login(user)
    forbidden_response = client.get(url)

    assert forbidden_response.status_code == 403

    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    response = client.get(url)

    assert response.status_code == 200
    assert b"Aniversariantes da semana" in response.content


@pytest.mark.django_db
def test_birthday_settings_save_updates_singleton(client, django_user_model):
    """Settings page should save the singleton configuration."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)

    response = client.post(reverse("birthdays:settings"), _settings_post_data())

    settings_obj = BirthdayReportSettings.get_solo()
    assert response.status_code == 302
    assert response.headers["Location"] == reverse("birthdays:settings")
    assert settings_obj.is_enabled is True
    assert settings_obj.recipients == ["leader@example.com"]


@pytest.mark.django_db
def test_generate_now_post_saves_settings_and_runs_manual_service(
    client,
    django_user_model,
    monkeypatch,
):
    """Generate now should be a POST action that saves settings before running."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    captured = {}

    def fake_process_manual(settings_obj):
        """Capture settings passed to manual generation."""
        captured["recipients"] = list(settings_obj.recipients)
        return BirthdayReportResult(no_birthdays=True)

    monkeypatch.setattr(
        "apps.birthdays.views.process_manual_birthday_report",
        fake_process_manual,
    )

    response = client.post(
        reverse("birthdays:settings"),
        _settings_post_data(action="generate_now", recipients_text="manual@example.com"),
    )

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("birthdays:history")
    assert captured["recipients"] == ["manual@example.com"]


@pytest.mark.django_db
def test_birthday_history_lists_latest_five_reports(client, django_user_model):
    """History page should list only the latest five birthday reports."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    for day in range(1, 7):
        BirthdayReport.objects.create(
            period_start=date(2026, 7, day),
            period_end=date(2026, 7, day + 6),
            member_count=day,
        )

    response = client.get(reverse("birthdays:history"))
    content = response.content.decode()

    assert response.status_code == 200
    assert response.content.count(b"aniversariante(s)") == 5
    assert "06/07/2026 a 12/07/2026" in content
    assert "2026-07-06" not in content


@pytest.mark.django_db
def test_birthday_report_image_requires_staff_and_serves_private_file(
    client,
    django_user_model,
    settings,
    tmp_path,
):
    """Report image view should serve the file only to staff users."""
    settings.MEDIA_ROOT = tmp_path
    report = _report_with_image()
    user = _create_user(django_user_model)
    client.force_login(user)

    forbidden_response = client.get(reverse("birthdays:image", args=[report.pk]))

    assert forbidden_response.status_code == 403

    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    response = client.get(reverse("birthdays:image", args=[report.pk]))

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/jpeg"


@pytest.mark.django_db
def test_birthday_report_images_redirect_to_presigned_s3_urls(
    client,
    django_user_model,
    monkeypatch,
    settings,
    tmp_path,
):
    """S3 report delivery should avoid server-side storage reads."""
    class PresignedS3Storage(S3Storage):
        """S3 storage double that records generated URL parameters."""

        calls: list[tuple[str, dict[str, str] | None]] = []

        def url(self, name, parameters=None, expire=None, http_method=None):
            """Return a deterministic presigned URL for assertions."""
            self.calls.append((name, parameters))
            return f"https://s3.example.com/{name}?signature=example"

    settings.MEDIA_ROOT = tmp_path
    report = _report_with_image()
    storage = object.__new__(PresignedS3Storage)
    storage.calls = []
    monkeypatch.setattr(BirthdayReport._meta.get_field("image"), "storage", storage)
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)

    image_response = client.get(reverse("birthdays:image", args=[report.pk]))
    download_response = client.get(reverse("birthdays:image_download", args=[report.pk]))

    assert image_response.status_code == 302
    assert image_response.headers["Location"] == (
        f"https://s3.example.com/{report.image.name}?signature=example"
    )
    assert download_response.status_code == 302
    assert storage.calls == [
        (report.image.name, None),
        (
            report.image.name,
            {
                "ResponseContentDisposition": (
                    f'attachment; filename="{report.image_filename}"'
                ),
                "ResponseContentType": "image/jpeg",
            },
        ),
    ]


@pytest.mark.django_db
def test_resend_accepts_only_post_and_uses_service(
    client,
    django_user_model,
    monkeypatch,
    settings,
    tmp_path,
):
    """Re-send action should reject GET and call the service on POST."""
    settings.MEDIA_ROOT = tmp_path
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    report = _report_with_image()
    captured = {}

    get_response = client.get(reverse("birthdays:resend", args=[report.pk]))
    assert get_response.status_code == 405

    def fake_resend(report_to_resend):
        """Capture the report passed to the resend service."""
        captured["pk"] = report_to_resend.pk
        return BirthdayReportResult(report=report_to_resend, email_sent=True)

    monkeypatch.setattr("apps.birthdays.views.resend_birthday_report", fake_resend)

    post_response = client.post(reverse("birthdays:resend", args=[report.pk]))

    assert post_response.status_code == 302
    assert post_response.headers["Location"] == reverse("birthdays:history")
    assert captured["pk"] == report.pk
