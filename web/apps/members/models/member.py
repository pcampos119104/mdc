"""Member model for the members app."""

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from .base import SoftDeleteModel


class Member(SoftDeleteModel):
    """Store the main registration data for a church member."""

    class RegistrationType(models.TextChoices):
        """Allowed registration type values for member records."""

        LEADERSHIP = "lideranca", "Liderança"
        PASTOR = "pastor", "Pastor"
        MEMBER = "membro", "Membro"

    class Classification(models.TextChoices):
        """Allowed service and ministry classification values for members."""

        CELEBRANDO = "celebrando", "Celebrando"
        SOUND_AND_MEDIA = "som_imagem", "Som e imagem"
        THEATER = "teatro", "Teatro"
        COMUNAKIDS = "comunakids", "ComunaKids"
        YOUTH = "jovens", "Jovens"
        WOMEN = "mulheres", "Mulheres"
        WORSHIP = "louvor", "Louvor"
        PASTORAL = "pastoral", "Pastoral"

    class Sex(models.TextChoices):
        """Allowed biological sex values for member records."""

        MALE = "male", "Masculino"
        FEMALE = "female", "Feminino"

    class MaritalStatus(models.TextChoices):
        """Allowed marital status values for member records."""

        SINGLE = "single", "Solteiro(a)"
        MARRIED = "married", "Casado(a)"
        STABLE_UNION = "stable_union", "União estável"
        DIVORCED = "divorced", "Divorciado(a)"
        WIDOWED = "widowed", "Viúvo(a)"

    name = models.CharField(max_length=255, help_text="Nome completo do membro.")
    photo = models.ImageField(
        upload_to="members/%Y/%m/",
        blank=True,
        null=True,
        help_text="Foto do membro para identificação visual no sistema.",
    )
    registration_type = models.CharField(
        max_length=20,
        choices=RegistrationType.choices,
        default=RegistrationType.MEMBER,
        help_text="Tipo de cadastro do membro na igreja.",
    )
    classifications = models.JSONField(
        blank=True,
        default=list,
        help_text="Classificações ministeriais vinculadas ao membro.",
    )
    cpf = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        unique=True,
        validators=[RegexValidator(r"^\d{11}$", "Informe um CPF com 11 dígitos.")],
        help_text="CPF do membro com 11 dígitos, sem pontos ou traço.",
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
        help_text="Data da aclamação do membro.",
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
    birthplace = models.CharField(
        max_length=255,
        blank=True,
        help_text="Cidade de nascimento ou naturalidade do membro.",
    )
    profession = models.CharField(
        max_length=255,
        blank=True,
        help_text="Profissão do membro.",
    )
    email = models.EmailField(
        blank=True,
        help_text="Endereço de e-mail principal do membro.",
    )
    father_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nome do pai do membro.",
    )
    mother_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nome da mãe do membro.",
    )
    spouse_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nome do cônjuge, quando houver.",
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
        help_text="Indica se o cadastro do membro está ativo no sistema.",
    )
    inactive_reason = models.TextField(
        blank=True,
        help_text="Motivo informado quando o cadastro do membro está inativo.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Data e hora em que o cadastro foi criado.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Data e hora da última atualização do cadastro.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        """Return the member name for admin and shell displays."""
        return self.name

    @property
    def initials(self):
        """Return up to two initials for avatar fallback displays."""
        name_parts = [part for part in self.name.split() if part]
        if not name_parts:
            return "?"

        return "".join(part[0].upper() for part in name_parts[:2])

    def get_classifications_display(self):
        """Return selected classifications as a comma-separated display string."""
        labels_by_value = dict(self.Classification.choices)
        labels = [
            labels_by_value[value]
            for value in self.classifications
            if value in labels_by_value
        ]
        return ", ".join(labels)

    def clean(self):
        """Validate inactive reason and selected classifications."""
        super().clean()

        inactive_reason = str(getattr(self, "inactive_reason", "") or "").strip()
        if not self.is_active and not inactive_reason:
            raise ValidationError(
                {"inactive_reason": "Informe o motivo para inativar o cadastro."}
            )

        classifications = self.classifications or []
        valid_classifications = {value for value, _label in self.Classification.choices}
        if not isinstance(classifications, list) or any(
            value not in valid_classifications for value in classifications
        ):
            raise ValidationError(
                {"classifications": "Selecione apenas classificações válidas."}
            )
