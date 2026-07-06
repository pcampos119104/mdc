"""Member model for the members app."""

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from .base import SoftDeleteModel


class Member(SoftDeleteModel):
    """Store the main registration data for a church member."""

    class Sex(models.TextChoices):
        """Allowed biological sex values for member records."""

        MALE = "male", "Masculino"
        FEMALE = "female", "Feminino"

    class MaritalStatus(models.TextChoices):
        """Allowed marital status values for member records."""

        SINGLE = "single", "Solteiro(a)"
        MARRIED = "married", "Casado(a)"
        STABLE_UNION = "stable_union", "Uniao estavel"
        DIVORCED = "divorced", "Divorciado(a)"
        WIDOWED = "widowed", "Viuvo(a)"

    name = models.CharField(max_length=255, help_text="Nome completo do membro.")
    registration_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Tipo de cadastro informado pela igreja, por exemplo: Lideranca.",
    )
    person_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Classificacao da pessoa, por exemplo: Pessoa, Lideranca ou Pastor.",
    )
    cpf = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        unique=True,
        validators=[RegexValidator(r"^\d{11}$", "Informe um CPF com 11 digitos.")],
        help_text="CPF do membro com 11 digitos, sem pontos ou traco.",
    )
    birth_date = models.DateField(
        blank=True,
        null=True,
        help_text="Data de nascimento do membro.",
    )
    baptism_date = models.DateField(
        blank=True,
        null=True,
        help_text="Data do batismo do membro.",
    )
    acclamation_date = models.DateField(
        blank=True,
        null=True,
        help_text="Data da aclamacao do membro.",
    )
    include_in_birthday_list = models.BooleanField(
        default=True,
        help_text="Indica se o membro deve aparecer na lista de aniversariantes.",
    )
    sex = models.CharField(
        max_length=6,
        blank=True,
        choices=Sex.choices,
        help_text="Sexo informado no cadastro.",
    )
    nationality = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nacionalidade do membro.",
    )
    birthplace = models.CharField(
        max_length=255,
        blank=True,
        help_text="Cidade de nascimento ou naturalidade do membro.",
    )
    email = models.EmailField(
        blank=True,
        help_text="Endereco de e-mail principal do membro.",
    )
    father_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nome do pai do membro.",
    )
    mother_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nome da mae do membro.",
    )
    spouse_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nome do conjuge, quando houver.",
    )
    marital_status = models.CharField(
        max_length=20,
        blank=True,
        choices=MaritalStatus.choices,
        help_text="Estado civil do membro.",
    )
    marriage_date = models.DateField(
        blank=True,
        null=True,
        help_text="Data do casamento, quando houver.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indica se o cadastro do membro esta ativo no sistema.",
    )
    inactive_reason = models.TextField(
        blank=True,
        help_text="Motivo informado quando o cadastro do membro esta inativo.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Data e hora em que o cadastro foi criado.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Data e hora da ultima atualizacao do cadastro.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        """Return the member name for admin and shell displays."""
        return self.name

    def clean(self):
        """Require an inactive reason when the member is marked inactive."""
        super().clean()

        inactive_reason = str(getattr(self, "inactive_reason", "") or "").strip()
        if not self.is_active and not inactive_reason:
            raise ValidationError(
                {"inactive_reason": "Informe o motivo para inativar o cadastro."}
            )
