"""Forms for birthday report settings."""

import re

from django import forms
from django.core.validators import EmailValidator

from .models import BirthdayReportSettings


class BirthdayReportSettingsForm(forms.ModelForm):
    """Validate the global birthday report settings form."""

    recipients_text = forms.CharField(
        label="Destinatários",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="Informe um e-mail por linha ou separe por vírgula/ponto e vírgula.",
    )

    class Meta:
        model = BirthdayReportSettings
        fields = ["is_enabled", "week_starts_on", "send_day"]
        labels = {
            "is_enabled": "Ativar envio automático",
            "week_starts_on": "Início da semana",
            "send_day": "Dia do envio",
        }

    def __init__(self, *args, **kwargs):
        """Initialize recipients from the stored JSON list."""
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["recipients_text"].initial = "\n".join(self.instance.recipients)

    def clean_recipients_text(self):
        """Normalize and validate a free-form recipient list."""
        raw_value = self.cleaned_data.get("recipients_text") or ""
        recipients = [
            email.strip()
            for email in re.split(r"[\n,;]+", raw_value)
            if email.strip()
        ]
        validator = EmailValidator()

        invalid_emails = []
        for email in recipients:
            try:
                validator(email)
            except forms.ValidationError:
                invalid_emails.append(email)

        if invalid_emails:
            raise forms.ValidationError(
                "E-mails inválidos: " + ", ".join(invalid_emails)
            )

        return recipients

    def clean(self):
        """Require recipients when automatic sending is active."""
        cleaned_data = super().clean()
        if cleaned_data.get("is_enabled") and not cleaned_data.get("recipients_text"):
            self.add_error(
                "recipients_text",
                "Informe ao menos um destinatário para ativar o envio automático.",
            )
        return cleaned_data

    def save(self, commit=True):
        """Persist normalized recipients on the singleton settings row."""
        instance = super().save(commit=False)
        instance.recipients = self.cleaned_data.get("recipients_text") or []
        if commit:
            instance.save()
            self.save_m2m()
        return instance
