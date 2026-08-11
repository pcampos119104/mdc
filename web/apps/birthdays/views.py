"""Views for birthday report settings, history and actions."""

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from storages.backends.s3 import S3Storage

from .forms import BirthdayReportSettingsForm
from .models import BirthdayReport, BirthdayReportSettings
from .permissions import birthday_admin_required
from .selectors import get_latest_birthday_reports
from .services.reports import process_manual_birthday_report, resend_birthday_report


def _add_report_result_messages(request, result, *, manual=False, resend=False):
    """Add user-facing feedback for a report processing result."""
    if result.no_birthdays:
        messages.info(request, "Não existem aniversariantes no período configurado.")
        return

    if result.generation_failed:
        messages.error(request, "Erro ao gerar a imagem dos aniversariantes.")
        return

    if result.image_created and not resend:
        messages.success(request, "Imagem dos aniversariantes criada e salva.")

    if result.email_sent:
        if resend:
            messages.success(request, "E-mail reenviado com sucesso.")
        else:
            messages.success(request, "E-mail enviado com sucesso.")
        return

    if result.email_failed:
        if resend:
            messages.error(request, "Falha ao reenviar o e-mail. A imagem foi preservada.")
        elif manual:
            messages.error(request, "A imagem foi criada, mas o envio do e-mail falhou.")
        else:
            messages.error(request, "Falha ao enviar o e-mail do relatório.")


@birthday_admin_required
def birthday_settings(request):
    """Display and update birthday report settings, including manual generation."""
    settings_obj = BirthdayReportSettings.get_solo()

    if request.method == "POST":
        form = BirthdayReportSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            settings_obj = form.save()
            action = request.POST.get("action", "save")
            if action == "generate_now":
                result = process_manual_birthday_report(settings_obj)
                _add_report_result_messages(request, result, manual=True)
                return redirect("birthdays:history")

            messages.success(request, "Configurações dos aniversariantes salvas.")
            return redirect("birthdays:settings")
    else:
        form = BirthdayReportSettingsForm(instance=settings_obj)

    return render(
        request,
        "birthdays/settings.html",
        {
            "form": form,
            "latest_reports": get_latest_birthday_reports(),
        },
    )


@birthday_admin_required
def birthday_report_history(request):
    """List the latest generated birthday reports."""
    return render(
        request,
        "birthdays/history.html",
        {
            "reports": get_latest_birthday_reports(),
        },
    )


def _open_report_image(report):
    """Open a report image for secure authenticated delivery."""
    if not report.image:
        raise Http404("Relatório sem imagem gerada.")
    try:
        report.image.open("rb")
    except OSError as exc:
        raise Http404("Imagem do relatório não encontrada.") from exc
    return report.image


def _report_image_url(report, *, as_attachment=False):
    """Return a presigned S3 GET URL for an authorized report image."""
    parameters = None
    if as_attachment:
        parameters = {
            "ResponseContentDisposition": (
                f'attachment; filename="{report.image_filename}"'
            ),
            "ResponseContentType": "image/jpeg",
        }

    return report.image.storage.url(report.image.name, parameters=parameters)


@birthday_admin_required
def birthday_report_image(request, pk):
    """Display a generated birthday report image to an authorized user."""
    report = get_object_or_404(BirthdayReport, pk=pk)
    if isinstance(report.image.storage, S3Storage):
        return redirect(_report_image_url(report))

    return FileResponse(_open_report_image(report), content_type="image/jpeg")


@birthday_admin_required
def birthday_report_image_download(request, pk):
    """Download a generated birthday report image to an authorized user."""
    report = get_object_or_404(BirthdayReport, pk=pk)
    if isinstance(report.image.storage, S3Storage):
        return redirect(_report_image_url(report, as_attachment=True))

    return FileResponse(
        _open_report_image(report),
        as_attachment=True,
        filename=report.image_filename,
        content_type="image/jpeg",
    )


@birthday_admin_required
@require_POST
def birthday_report_resend(request, pk):
    """Resend a stored birthday report image to its preserved recipients."""
    report = get_object_or_404(BirthdayReport, pk=pk)
    result = resend_birthday_report(report)
    _add_report_result_messages(request, result, resend=True)
    return redirect("birthdays:history")
