"""Models for the Natal Feliz campaign."""

from django.db import models


class Child(models.Model):
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

    class Meta:
        ordering = ["name"]

    def __str__(self):
        """Return the child name for admin and shell displays."""
        return self.name
