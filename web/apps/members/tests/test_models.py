"""Tests for members app models."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.members.models import Address, Member, Phone


@pytest.mark.django_db
def test_member_can_be_created_with_initial_fields():
    """Member should persist the initial registration fields."""
    member = Member.objects.create(
        name="Ailton Quaresma Trindade Junior",
        registration_type="Lideranca",
        person_type="Pessoa",
        cpf="22406088898",
        birth_date=date(1982, 3, 29),
        baptism_date=date(1999, 6, 12),
        acclamation_date=date(2020, 8, 9),
        sex=Member.Sex.MALE,
        nationality="Brazil",
        birthplace="Sao Paulo SP",
        email="ailtontrindade84@gmail.com",
        father_name="Ailton Quaresma Trindade",
        mother_name="Josefa Pinheiro dos Santos",
        spouse_name="Walquiria Batista dos Santos",
        marital_status=Member.MaritalStatus.MARRIED,
        marriage_date=date(2010, 5, 1),
    )

    member.full_clean()
    assert member.pk is not None
    assert member.baptism_date == date(1999, 6, 12)
    assert member.acclamation_date == date(2020, 8, 9)
    assert member.is_active is True
    assert member.include_in_birthday_list is True
    assert str(member) == member.name


@pytest.mark.django_db
def test_member_cpf_is_unique_when_present_and_optional_when_empty():
    """CPF should be unique only when it is informed."""
    Member.objects.create(name="Membro sem CPF")
    Member.objects.create(name="Outro membro sem CPF")
    Member.objects.create(name="Membro com CPF", cpf="12345678901")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Member.objects.create(name="CPF duplicado", cpf="12345678901")


def test_member_rejects_invalid_structured_values():
    """Structured member fields should validate constrained values."""
    member = Member(name="Maria Silva", cpf="123", sex="outro")

    with pytest.raises(ValidationError):
        member.full_clean()


def test_member_requires_inactive_reason_when_inactive():
    """Inactive members should include the reason for inactivation."""
    member = Member(name="Maria Silva", is_active=False)

    with pytest.raises(ValidationError) as exc_info:
        member.full_clean()

    assert "inactive_reason" in exc_info.value.message_dict


@pytest.mark.django_db
def test_member_address_belongs_to_member():
    """Address should be linked to a single member."""
    member = Member.objects.create(name="Ailton Quaresma Trindade Junior")
    address = Address.objects.create(
        member=member,
        postal_code="04166003",
        country="Brazil",
        state="SP",
        city="Sao Paulo",
        street="Avenida Padre Arlindo Vieira",
        street_number="3590",
        complement="Casa 02",
        district="Jardim Vergueiro",
    )

    assert address.member == member
    address.full_clean()
    assert str(address) == f"Address for {member.name}"


@pytest.mark.django_db
def test_member_phone_belongs_to_member():
    """Phone numbers should be linked to a member."""
    member = Member.objects.create(name="Ailton Quaresma Trindade Junior")
    phone = Phone.objects.create(
        member=member,
        kind=Phone.KIND_MOBILE,
        number="11970478945",
        is_primary=True,
        receives_sms=True,
        has_whatsapp=True,
    )

    assert phone.member == member
    phone.full_clean()
    assert str(phone) == f"{member.name} - 11970478945"


def test_contact_data_rejects_invalid_numeric_values():
    """Address and phone numeric fields should reject malformed values."""
    member = Member(name="Maria Silva")
    address = Address(member=member, postal_code="01001-000", state="Sao Paulo")
    phone = Phone(member=member, kind=Phone.KIND_MOBILE, number="abc")

    with pytest.raises(ValidationError):
        address.full_clean()

    with pytest.raises(ValidationError):
        phone.full_clean()


@pytest.mark.django_db
def test_member_can_be_soft_deleted_restored_and_hard_deleted():
    """Member soft delete should hide records until they are restored."""
    member = Member.objects.create(name="Ailton Quaresma Trindade Junior")
    member_pk = member.pk

    deleted_count, deleted_by_model = member.delete()

    assert deleted_count == 1
    assert deleted_by_model == {"members.Member": 1}
    assert not Member.objects.filter(pk=member_pk).exists()

    deleted_member = Member.all_objects.get(pk=member_pk)
    assert deleted_member.deleted_at is not None

    restored_count, restored_by_model = deleted_member.restore()

    assert restored_count == 1
    assert restored_by_model == {"members.Member": 1}
    assert Member.objects.filter(pk=member_pk).exists()

    restored_member = Member.objects.get(pk=member_pk)
    restored_member.hard_delete()

    assert not Member.all_objects.filter(pk=member_pk).exists()


def test_member_fields_expose_help_texts():
    """Important member fields should expose Portuguese helper texts."""
    assert Member._meta.get_field("name").help_text == "Nome completo do membro."
    assert (
        Member._meta.get_field("cpf").help_text
        == "CPF do membro com 11 digitos, sem pontos ou traco."
    )
    assert (
        Member._meta.get_field("marriage_date").help_text
        == "Data do casamento, quando houver."
    )
    assert (
        Member._meta.get_field("include_in_birthday_list").help_text
        == "Indica se o membro deve aparecer na lista de aniversariantes."
    )
    assert (
        Member._meta.get_field("baptism_date").help_text
        == "Data do batismo do membro."
    )
    assert (
        Member._meta.get_field("acclamation_date").help_text
        == "Data da aclamacao do membro."
    )
    assert (
        Member._meta.get_field("inactive_reason").help_text
        == "Motivo informado quando o cadastro do membro esta inativo."
    )
    assert (
        Phone._meta.get_field("has_whatsapp").help_text
        == "Indica se este telefone possui WhatsApp."
    )
