"""E-mail services for birthday reports."""

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone


class BirthdayReportEmailError(Exception):
    """Raised when the birthday report e-mail cannot be sent."""


def build_birthday_report_subject(period_start, period_end):
    """Build the subject used for birthday report e-mails."""
    return (
        "Aniversariantes da semana - "
        f"{period_start:%d/%m/%Y} a {period_end:%d/%m/%Y}"
    )


def sanitize_exception_message(exc):
    """Return a useful error message without known configured secrets."""
    message = str(exc) or "Erro sem detalhes adicionais."
    for secret in (
        getattr(settings, "EMAIL_HOST_USER", ""),
        getattr(settings, "EMAIL_HOST_PASSWORD", ""),
        getattr(settings, "SECRET_KEY", ""),
    ):
        if secret:
            message = message.replace(secret, "[redacted]")

    return f"{exc.__class__.__name__}: {message}"[:1000]


def send_birthday_report_email(report, *, image_content=None):
    """Send a birthday report e-mail with the supplied or stored JPEG attached."""
    if not report.recipients:
        raise BirthdayReportEmailError(
            "Nenhum destinatário configurado para este relatório."
        )

    if not report.image:
        raise BirthdayReportEmailError("O relatório não possui imagem para envio.")

    subject = report.email_subject or build_birthday_report_subject(
        report.period_start,
        report.period_end,
    )
    body = (
        "Segue em anexo a imagem com os aniversariantes da semana "
        f"de {report.period_start:%d/%m/%Y} a {report.period_end:%d/%m/%Y}."
    )
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=report.recipients,
    )

    if image_content is None:
        report.image.open("rb")
        try:
            image_content = report.image.read()
        finally:
            report.image.close()

    message.attach(report.image_filename, image_content, "image/jpeg")
    sent_count = message.send(fail_silently=False)
    if sent_count == 0:
        raise BirthdayReportEmailError(
            "O backend de e-mail não confirmou o envio para nenhum destinatário."
        )

    return timezone.now()
