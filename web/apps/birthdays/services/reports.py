"""Main orchestration services for birthday reports."""

from dataclasses import dataclass, field

from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.utils import timezone

from apps.birthdays.selectors import (
    get_automatic_report_for_period,
    get_birthday_members_for_period,
)

from ..models import BirthdayReport
from .dates import calculate_week_period, get_local_now, is_scheduled_report_due
from .emails import (
    build_birthday_report_subject,
    sanitize_exception_message,
    send_birthday_report_email,
)
from .images import generate_birthday_report_image


@dataclass
class BirthdayReportResult:
    """Describe the result of a birthday report processing attempt."""

    report: BirthdayReport | None = None
    members: list = field(default_factory=list)
    skipped_reason: str = ""
    image_created: bool = False
    email_sent: bool = False
    email_failed: bool = False
    generation_failed: bool = False
    no_birthdays: bool = False

    @property
    def skipped(self):
        """Return whether processing was skipped before creating a report."""
        return bool(self.skipped_reason)


def _create_pending_report(settings_obj, period_start, period_end, *, is_automatic):
    """Create the initial pending report row preserving current recipients."""
    return BirthdayReport.objects.create(
        period_start=period_start,
        period_end=period_end,
        recipients=list(settings_obj.recipients),
        member_count=0,
        email_subject=build_birthday_report_subject(period_start, period_end),
        is_automatic=is_automatic,
    )


def _set_report_failed(report, exc, *, sent_at=None):
    """Persist a safe failure message on a report."""
    report.send_status = BirthdayReport.SendStatus.FAILED
    report.error_message = sanitize_exception_message(exc)
    if sent_at is not None:
        report.sent_at = sent_at
    report.save(update_fields=["send_status", "error_message", "sent_at", "updated_at"])


def _send_and_update_report(report):
    """Send a report e-mail and update business status fields."""
    attempted_at = timezone.now()
    try:
        sent_at = send_birthday_report_email(report)
    except Exception as exc:
        report.send_status = BirthdayReport.SendStatus.FAILED
        report.sent_at = attempted_at
        report.error_message = sanitize_exception_message(exc)
        report.save(update_fields=["send_status", "sent_at", "error_message", "updated_at"])
        return False

    report.send_status = BirthdayReport.SendStatus.SENT
    report.sent_at = sent_at
    report.error_message = ""
    report.save(update_fields=["send_status", "sent_at", "error_message", "updated_at"])
    return True


def create_birthday_report(settings_obj, period_start, period_end, *, is_automatic):
    """Create, render, store and send a birthday report for a period."""
    if is_automatic and get_automatic_report_for_period(period_start, period_end):
        return BirthdayReportResult(
            skipped_reason="Relatório automático deste período já foi processado."
        )

    try:
        report = _create_pending_report(
            settings_obj,
            period_start,
            period_end,
            is_automatic=is_automatic,
        )
    except IntegrityError:
        if is_automatic:
            return BirthdayReportResult(
                skipped_reason="Relatório automático deste período já foi processado."
            )
        raise

    members = get_birthday_members_for_period(period_start, period_end)
    report.member_count = len(members)

    if not members:
        report.send_status = BirthdayReport.SendStatus.NO_BIRTHDAYS
        report.error_message = ""
        report.save(update_fields=["member_count", "send_status", "error_message", "updated_at"])
        return BirthdayReportResult(report=report, members=members, no_birthdays=True)

    try:
        image_content = generate_birthday_report_image(members, period_start, period_end)
    except Exception as exc:
        report.member_count = len(members)
        report.save(update_fields=["member_count", "updated_at"])
        _set_report_failed(report, exc)
        return BirthdayReportResult(
            report=report,
            members=members,
            generation_failed=True,
        )

    report.image.save(report.image_filename, ContentFile(image_content), save=False)
    report.member_count = len(members)
    report.save(update_fields=["image", "member_count", "updated_at"])

    email_sent = _send_and_update_report(report)
    return BirthdayReportResult(
        report=report,
        members=members,
        image_created=True,
        email_sent=email_sent,
        email_failed=not email_sent,
    )


def process_manual_birthday_report(settings_obj, now=None):
    """Run the birthday report flow immediately for the current configured week."""
    local_now = get_local_now(now)
    period_start, period_end = calculate_week_period(
        local_now.date(),
        settings_obj.week_starts_on,
    )
    return create_birthday_report(
        settings_obj,
        period_start,
        period_end,
        is_automatic=False,
    )


def process_scheduled_birthday_report(now=None):
    """Run the scheduled birthday report flow when it is due."""
    from ..models import BirthdayReportSettings

    settings_obj = BirthdayReportSettings.get_solo()
    if not settings_obj.is_enabled:
        return BirthdayReportResult(skipped_reason="Funcionalidade desativada.")

    is_due, period_start, period_end, scheduled_at, local_now = is_scheduled_report_due(
        settings_obj,
        now=now,
    )
    if not is_due:
        return BirthdayReportResult(
            skipped_reason=(
                "Ainda não chegou o agendamento. "
                f"Agora: {local_now:%d/%m/%Y %H:%M}; "
                f"agendado: {scheduled_at:%d/%m/%Y %H:%M}."
            )
        )

    return create_birthday_report(
        settings_obj,
        period_start,
        period_end,
        is_automatic=True,
    )


def resend_birthday_report(report):
    """Resend a stored birthday report image to its preserved recipients."""
    if not report.image:
        report.send_status = BirthdayReport.SendStatus.FAILED
        report.sent_at = timezone.now()
        report.error_message = "O relatório não possui imagem para reenvio."
        report.save(update_fields=["send_status", "sent_at", "error_message", "updated_at"])
        return BirthdayReportResult(report=report, email_failed=True)

    email_sent = _send_and_update_report(report)
    return BirthdayReportResult(
        report=report,
        image_created=True,
        email_sent=email_sent,
        email_failed=not email_sent,
    )
