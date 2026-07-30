"""Models for birthday report settings and history."""

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import models
from django.db.models import Q


WEEKDAY_CHOICES = [
    (0, "Segunda-feira"),
    (1, "Terça-feira"),
    (2, "Quarta-feira"),
    (3, "Quinta-feira"),
    (4, "Sexta-feira"),
    (5, "Sábado"),
    (6, "Domingo"),
]


def validate_email_list(value):
    """Validate a JSON list containing only valid e-mail addresses."""
    if not isinstance(value, list):
        raise ValidationError("Informe uma lista de e-mails válida.")

    validator = EmailValidator()
    errors = []
    for email in value:
        if not isinstance(email, str):
            errors.append("Informe apenas endereços de e-mail em texto.")
            continue

        try:
            validator(email)
        except ValidationError:
            errors.append(f"E-mail inválido: {email}")

    if errors:
        raise ValidationError(errors)


class BirthdayReportSettings(models.Model):
    """Store the global settings for weekly birthday report delivery."""

    is_enabled = models.BooleanField(
        default=False,
        help_text="Indica se o envio automático de aniversariantes está ativo.",
    )
    week_starts_on = models.PositiveSmallIntegerField(
        choices=WEEKDAY_CHOICES,
        default=0,
        help_text="Dia considerado como início da semana de aniversariantes.",
    )
    send_day = models.PositiveSmallIntegerField(
        choices=WEEKDAY_CHOICES,
        default=0,
        help_text="Dia da semana em que o e-mail deve ser enviado.",
    )
    recipients = models.JSONField(
        blank=True,
        default=list,
        validators=[validate_email_list],
        help_text="Lista de destinatários do relatório semanal.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Data e hora em que a configuração foi criada.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Data e hora da última atualização da configuração.",
    )

    class Meta:
        verbose_name = "Birthday report setting"
        verbose_name_plural = "Birthday report settings"

    def __str__(self):
        """Return a readable name for admin and shell displays."""
        return "Configuração de aniversariantes da semana"

    def save(self, *args, **kwargs):
        """Keep a single global settings row by forcing a stable primary key."""
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Avoid deleting the singleton settings row from application code."""
        raise ValidationError("A configuração global não pode ser removida.")

    @classmethod
    def get_solo(cls):
        """Return the single global settings row, creating it when needed."""
        settings_obj, _created = cls.objects.get_or_create(pk=1)
        return settings_obj


def birthday_report_upload_to(instance, filename):
    """Build a storage path that identifies the birthday report period."""
    return (
        "birthday_reports/"
        f"{instance.period_start:%Y/%m}/"
        f"aniversariantes_{instance.period_start:%Y-%m-%d}_"
        f"{instance.period_end:%Y-%m-%d}.jpg"
    )


class BirthdayReport(models.Model):
    """Store generated weekly birthday report images and e-mail status."""

    class SendStatus(models.TextChoices):
        """Allowed delivery statuses for a birthday report."""

        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviado com sucesso"
        FAILED = "failed", "Falhou"
        NO_BIRTHDAYS = "no_birthdays", "Sem aniversariantes"

    period_start = models.DateField(
        help_text="Data inicial do período contemplado no relatório.",
    )
    period_end = models.DateField(
        help_text="Data final do período contemplado no relatório.",
    )
    image = models.ImageField(
        upload_to=birthday_report_upload_to,
        blank=True,
        null=True,
        help_text="Imagem JPEG gerada para o relatório.",
    )
    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Data e hora em que o relatório foi gerado.",
    )
    send_status = models.CharField(
        max_length=20,
        choices=SendStatus.choices,
        default=SendStatus.PENDING,
        help_text="Status do envio de e-mail do relatório.",
    )
    sent_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Data e hora da última tentativa de envio do relatório.",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Mensagem segura com detalhes úteis da falha, quando houver.",
    )
    recipients = models.JSONField(
        blank=True,
        default=list,
        validators=[validate_email_list],
        help_text="Destinatários usados no envio deste relatório.",
    )
    member_count = models.PositiveIntegerField(
        default=0,
        help_text="Quantidade de membros presentes no relatório.",
    )
    email_subject = models.CharField(
        max_length=255,
        blank=True,
        help_text="Assunto do e-mail enviado para este relatório.",
    )
    is_automatic = models.BooleanField(
        default=False,
        help_text="Indica se o relatório foi criado pelo processamento automático.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Data e hora da última atualização do relatório.",
    )

    class Meta:
        ordering = ["-generated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["period_start", "period_end"],
                condition=Q(is_automatic=True),
                name="unique_automatic_birthday_report_period",
            )
        ]
        indexes = [
            models.Index(fields=["-generated_at"], name="birthday_report_generated_idx"),
        ]

    def __str__(self):
        """Return a readable period label for admin and shell displays."""
        return f"Aniversariantes {self.period_start:%d/%m/%Y} a {self.period_end:%d/%m/%Y}"

    @property
    def image_filename(self):
        """Return the download filename for the generated image."""
        return (
            f"aniversariantes_{self.period_start:%Y-%m-%d}_"
            f"{self.period_end:%Y-%m-%d}.jpg"
        )
