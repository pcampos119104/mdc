"""Tests for birthday report settings forms."""

from apps.birthdays.forms import BirthdayReportSettingsForm


def _settings_form_data(**overrides):
    """Return valid settings form data with optional overrides."""
    data = {
        "is_enabled": "on",
        "week_starts_on": "0",
        "send_day": "2",
        "recipients_text": "leader@example.com\nsecretaria@example.com",
    }
    data.update(overrides)
    return data


def test_settings_form_normalizes_recipient_list():
    """Settings form should accept common separators for recipient e-mails."""
    form = BirthdayReportSettingsForm(
        data=_settings_form_data(
            recipients_text="leader@example.com, secretaria@example.com;pastor@example.com"
        )
    )

    assert form.is_valid()
    assert form.cleaned_data["recipients_text"] == [
        "leader@example.com",
        "secretaria@example.com",
        "pastor@example.com",
    ]


def test_settings_form_rejects_invalid_recipient_email():
    """Settings form should reject invalid recipient e-mail addresses."""
    form = BirthdayReportSettingsForm(
        data=_settings_form_data(recipients_text="leader@example.com\ninvalid-email")
    )

    assert not form.is_valid()
    assert "recipients_text" in form.errors


def test_settings_form_requires_recipients_when_enabled():
    """Enabled automatic sending should require at least one recipient."""
    form = BirthdayReportSettingsForm(data=_settings_form_data(recipients_text=""))

    assert not form.is_valid()
    assert "recipients_text" in form.errors


def test_settings_form_allows_empty_recipients_when_disabled():
    """Disabled automatic sending should allow storing no recipients."""
    data = _settings_form_data(recipients_text="")
    data.pop("is_enabled")
    form = BirthdayReportSettingsForm(data=data)

    assert form.is_valid()
    assert form.cleaned_data["recipients_text"] == []
