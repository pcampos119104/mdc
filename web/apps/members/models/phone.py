"""Phone model for the members app."""

from django.core.validators import RegexValidator
from django.db import models

from .member import Member


class Phone(models.Model):
    """Store phone numbers associated with a church member."""

    KIND_MOBILE = "mobile"
    KIND_HOME = "home"
    KIND_WORK = "work"
    KIND_CONTACT = "contact"
    KIND_CHOICES = [
        (KIND_MOBILE, "Mobile"),
        (KIND_HOME, "Home"),
        (KIND_WORK, "Work"),
        (KIND_CONTACT, "Contact"),
    ]

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="phones",
        help_text="Membro ao qual este telefone pertence.",
    )
    kind = models.CharField(
        max_length=20,
        choices=KIND_CHOICES,
        help_text="Tipo do telefone, como celular, residencial, comercial ou contato.",
    )
    number = models.CharField(
        max_length=15,
        validators=[RegexValidator(r"^\d{8,15}$", "Informe somente digitos no telefone.")],
        help_text="Numero de telefone com DDD e somente digitos.",
    )
    contact_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nome do contato relacionado a este telefone, quando aplicavel.",
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Indica se este e o telefone principal do membro.",
    )
    has_whatsapp = models.BooleanField(
        default=False,
        help_text="Indica se este telefone possui WhatsApp.",
    )

    class Meta:
        ordering = ["member__name", "kind", "number"]

    def __str__(self):
        """Return a readable label for the member phone number."""
        return f"{self.member.name} - {self.number}"
