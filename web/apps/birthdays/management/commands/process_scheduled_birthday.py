"""Process the scheduled weekly birthday report."""

from django.core.management.base import BaseCommand, CommandError

from apps.birthdays.services.reports import process_scheduled_birthday_report


class Command(BaseCommand):
    """Generate and e-mail the scheduled weekly birthday report when due."""

    help = "Generate, store and e-mail the scheduled weekly birthday report when due."

    def handle(self, *args, **options):
        """Run scheduled birthday processing and print clear operational logs."""
        try:
            result = process_scheduled_birthday_report()
        except Exception as exc:
            raise CommandError(f"Falha inesperada ao processar aniversariantes: {exc}") from exc

        if result.skipped:
            self.stdout.write(self.style.WARNING(f"Execução ignorada: {result.skipped_reason}"))
            return

        report = result.report
        if report is None:
            self.stdout.write(self.style.WARNING("Execução ignorada: nenhum relatório criado."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                "Relatório criado: "
                f"{report.period_start:%d/%m/%Y} a {report.period_end:%d/%m/%Y} "
                f"(#{report.pk})."
            )
        )

        if result.no_birthdays:
            self.stdout.write("Sem aniversariantes no período; e-mail não enviado.")
            return

        if result.generation_failed:
            self.stderr.write(
                self.style.ERROR(f"Falha na geração da imagem: {report.error_message}")
            )
            return

        if result.email_sent:
            self.stdout.write(self.style.SUCCESS("E-mail enviado com sucesso."))
            return

        if result.email_failed:
            self.stderr.write(
                self.style.ERROR(f"Falha no envio do e-mail: {report.error_message}")
            )
