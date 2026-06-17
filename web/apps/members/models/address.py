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
        help_text="Membro ao qual este endereco pertence.",
    )
    postal_code = models.CharField(
        max_length=8,
        blank=True,
        validators=[RegexValidator(r"^\d{8}$", "Informe um CEP com 8 digitos.")],
        help_text="CEP do endereco residencial com 8 digitos, sem traco.",
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        help_text="Pais do endereco residencial.",
    )
    state = models.CharField(
        max_length=2,
        blank=True,
        help_text="UF do endereco residencial.",
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="Cidade do endereco residencial.",
    )
    street = models.CharField(
        max_length=255,
        blank=True,
        help_text="Logradouro do endereco residencial.",
    )
    street_number = models.CharField(
        max_length=30,
        blank=True,
        help_text="Numero do endereco residencial.",
    )
    complement = models.CharField(
        max_length=255,
        blank=True,
        help_text="Complemento do endereco, como casa, bloco ou apartamento.",
    )
    district = models.CharField(
        max_length=255,
        blank=True,
        help_text="Bairro do endereco residencial.",
    )

    def __str__(self):
        """Return a readable label for the member address."""
        return f"Address for {self.member.name}"
