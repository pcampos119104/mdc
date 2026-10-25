"""Models for the Natal Feliz campaign."""

from django.db import models
from django.utils import timezone

from apps.members.models import Member, SoftDeleteModel


def current_year():
    """Return the current year for compatibility with the historical migration."""
    return timezone.localdate().year


class Child(SoftDeleteModel):
    """Store a child who may receive a Christmas gift."""

    name = models.CharField(
        max_length=255,
        help_text="Nome completo da criança.",
    )
    mother_name = models.CharField(
        max_length=255,
        help_text="Nome completo da mãe da criança.",
    )
    birth_date = models.DateField(
        help_text="Data de nascimento da criança.",
    )
    clothing_size = models.PositiveSmallIntegerField(
        null=True,
        help_text="Número do tamanho da roupa usada pela criança.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        """Return the child name for admin and shell displays."""
        return self.name


class ChristmasEvent(models.Model):
    """Store a scheduled Natal Feliz event."""

    name = models.CharField(
        max_length=255,
        help_text="Nome do evento Natal Feliz.",
    )
    event_date = models.DateField(
        help_text="Data em que o evento será realizado.",
    )
    event_time = models.TimeField(
        help_text="Horário em que o evento será realizado.",
    )
    label_note = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Observação opcional exibida nas etiquetas do evento.",
    )

    class Meta:
        ordering = ["-event_date", "-event_time", "name"]

    def __str__(self):
        """Return the event name for admin and shell displays."""
        return self.name


class ChristmasSponsorship(models.Model):
    """Relate an eligible sponsor to a child in a Natal Feliz event."""

    event = models.ForeignKey(
        ChristmasEvent,
        on_delete=models.CASCADE,
        related_name="sponsorships",
        help_text="Evento Natal Feliz ao qual o apadrinhamento pertence.",
    )
    sponsor = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="christmas_sponsorships",
        help_text="Pessoa responsável pelo presente da criança.",
    )
    child = models.ForeignKey(
        Child,
        on_delete=models.PROTECT,
        related_name="christmas_sponsorships",
        help_text="Criança que receberá o presente.",
    )
    class Meta:
        ordering = ["child__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "child"],
                name="uniq_christmas_event_child",
            )
        ]

    def __str__(self):
        """Return a readable description of the sponsorship."""
        return f"{self.child} — {self.sponsor} ({self.event})"
