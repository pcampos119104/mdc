"""Database models for church members and their contact data."""

from django.db import models


class Member(models.Model):
    """Store the main registration data for a church member."""

    name = models.CharField(max_length=255)
    registration_type = models.CharField(max_length=100, blank=True)
    person_type = models.CharField(max_length=100, blank=True)
    member_type = models.CharField(max_length=100, blank=True)
    cpf = models.CharField(max_length=14, blank=True)
    birth_date = models.DateField(blank=True, null=True)
    sex = models.CharField(max_length=50, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    birthplace = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    father_name = models.CharField(max_length=255, blank=True)
    mother_name = models.CharField(max_length=255, blank=True)
    spouse_name = models.CharField(max_length=255, blank=True)
    marital_status = models.CharField(max_length=50, blank=True)
    marriage_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        """Return the member name for admin and shell displays."""
        return self.name


class MemberAddress(models.Model):
    """Store the residential address details for a church member."""

    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name="address")
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    street = models.CharField(max_length=255, blank=True)
    street_number = models.CharField(max_length=30, blank=True)
    complement = models.CharField(max_length=255, blank=True)
    district = models.CharField(max_length=255, blank=True)

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

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="phones")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    number = models.CharField(max_length=30)
    contact_name = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    receives_sms = models.BooleanField(default=False)
    has_whatsapp = models.BooleanField(default=False)

    class Meta:
        ordering = ["member__name", "kind", "number"]

    def __str__(self):
        """Return a readable label for the member phone number."""
        return f"{self.member.name} - {self.number}"
