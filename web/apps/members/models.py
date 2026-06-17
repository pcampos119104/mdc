"""Database models for church members and their contact data."""

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet with soft delete helpers for records kept in the database."""

    def alive(self):
        """Return records that were not soft deleted."""
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        """Return records that were soft deleted."""
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        """Soft delete records in this queryset."""
        now = timezone.now()
        update_values = {"deleted_at": now}

        if any(field.name == "updated_at" for field in self.model._meta.fields):
            update_values["updated_at"] = now

        count = self.alive().update(**update_values)
        return count, {self.model._meta.label: count}

    def hard_delete(self):
        """Permanently delete records in this queryset."""
        return super().delete()


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager that hides soft-deleted records."""

    def get_queryset(self):
        """Return only records that were not soft deleted."""
        return super().get_queryset().alive()


class SoftDeleteModel(models.Model):
    """Abstract base model for records that should be removed logically."""

    deleted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Data e hora em que o registro foi removido logicamente.",
    )

    objects = SoftDeleteManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """Soft delete this record without removing it from the database."""
        if self.pk is None:
            raise ValueError("Cannot soft delete an unsaved object.")

        if self.deleted_at is not None:
            return 0, {self._meta.label: 0}

        self.deleted_at = timezone.now()
        update_fields = ["deleted_at"]

        if any(field.name == "updated_at" for field in self._meta.fields):
            update_fields.append("updated_at")

        self.save(using=using, update_fields=update_fields)
        return 1, {self._meta.label: 1}

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete this record from the database."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self, using=None):
        """Restore a previously soft-deleted record."""
        if self.pk is None:
            raise ValueError("Cannot restore an unsaved object.")

        if self.deleted_at is None:
            return 0, {self._meta.label: 0}

        self.deleted_at = None
        update_fields = ["deleted_at"]

        if any(field.name == "updated_at" for field in self._meta.fields):
            update_fields.append("updated_at")

        self.save(using=using, update_fields=update_fields)
        return 1, {self._meta.label: 1}


class Member(SoftDeleteModel):
    """Store the main registration data for a church member."""

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
    member_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Tipo de membro ou area principal de atuacao.",
    )
    cpf = models.CharField(
        max_length=14,
        blank=True,
        help_text="CPF do membro no formato brasileiro.",
    )
    birth_date = models.DateField(
        blank=True,
        null=True,
        help_text="Data de nascimento do membro.",
    )
    sex = models.CharField(
        max_length=50,
        blank=True,
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
        max_length=50,
        blank=True,
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


class MemberAddress(models.Model):
    """Store the residential address details for a church member."""

    member = models.OneToOneField(
        Member,
        on_delete=models.CASCADE,
        related_name="address",
        help_text="Membro ao qual este endereco pertence.",
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="CEP do endereco residencial.",
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        help_text="Pais do endereco residencial.",
    )
    state = models.CharField(
        max_length=100,
        blank=True,
        help_text="Estado do endereco residencial.",
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


class MemberPhone(models.Model):
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
    number = models.CharField(max_length=30, help_text="Numero de telefone.")
    contact_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nome do contato relacionado a este telefone, quando aplicavel.",
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Indica se este e o telefone principal do membro.",
    )
    receives_sms = models.BooleanField(
        default=False,
        help_text="Indica se este telefone pode receber SMS.",
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
