"""Address model for the members app."""

from django.core.validators import RegexValidator
from django.db import models

from .member import Member


class Address(models.Model):
    """Store the residential address details for a church member."""

    member = models.OneToOneField(
        Member,
        on_delete=models.CASCADE,
        related_name="address",
        help_text="Membro ao qual este endereço pertence.",
    )
    postal_code = models.CharField(
        max_length=8,
        blank=True,
        validators=[RegexValidator(r"^\d{8}$", "Informe um CEP com 8 dígitos.")],
        help_text="CEP do endereço residencial com 8 dígitos, sem traço.",
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        help_text="País do endereço residencial.",
    )
    state = models.CharField(
        max_length=2,
        blank=True,
        help_text="UF do endereço residencial.",
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="Cidade do endereço residencial.",
    )
    street = models.CharField(
        max_length=255,
        blank=True,
        help_text="Logradouro do endereço residencial.",
    )
    street_number = models.CharField(
        max_length=30,
        blank=True,
        help_text="Número do endereço residencial.",
    )
    complement = models.CharField(
        max_length=255,
        blank=True,
        help_text="Complemento do endereço, como casa, bloco ou apartamento.",
    )
    district = models.CharField(
        max_length=255,
        blank=True,
        help_text="Bairro do endereço residencial.",
    )

    def __str__(self):
        """Return a readable label for the member address."""
        return f"Address for {self.member.name}"
