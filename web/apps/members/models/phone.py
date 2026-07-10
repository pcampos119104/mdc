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
        (KIND_MOBILE, "Celular"),
        (KIND_HOME, "Residencial"),
        (KIND_WORK, "Comercial"),
        (KIND_CONTACT, "Contato"),
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
        validators=[RegexValidator(r"^\d{8,15}$", "Informe somente dígitos no telefone.")],
        help_text="Número de telefone com DDD e somente dígitos.",
    )
    contact_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nome do contato relacionado a este telefone, quando aplicável.",
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Indica se este é o telefone principal do membro.",
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
