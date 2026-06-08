"""Tests for members app models."""

from datetime import date

import pytest

from apps.members.models import Member, MemberAddress, MemberPhone


@pytest.mark.django_db
def test_member_can_be_created_with_initial_fields():
    """Member should persist the initial registration fields."""
    member = Member.objects.create(
        name="Ailton Quaresma Trindade Junior",
        registration_type="Lideranca",
        person_type="Pessoa",
        member_type="Presbitero",
        cpf="224.060.888-98",
        birth_date=date(1982, 3, 29),
        sex="Male",
        nationality="Brazil",
        birthplace="Sao Paulo SP",
        email="ailtontrindade84@gmail.com",
        father_name="Ailton Quaresma Trindade",
        mother_name="Josefa Pinheiro dos Santos",
        spouse_name="Walquiria Batista dos Santos",
        marital_status="Married",
        marriage_date=date(2010, 5, 1),
    )

    assert member.pk is not None
    assert member.is_active is True
    assert str(member) == member.name


@pytest.mark.django_db
def test_member_address_belongs_to_member():
    """Address should be linked to a single member."""
    member = Member.objects.create(name="Ailton Quaresma Trindade Junior")
    address = MemberAddress.objects.create(
        member=member,
        postal_code="04166003",
        country="Brazil",
        state="Sao Paulo",
        city="Sao Paulo",
        street="Avenida Padre Arlindo Vieira",
        street_number="3590",
        complement="Casa 02",
        district="Jardim Vergueiro",
    )

    assert address.member == member
    assert str(address) == f"Address for {member.name}"


@pytest.mark.django_db
def test_member_phone_belongs_to_member():
    """Phone numbers should be linked to a member."""
    member = Member.objects.create(name="Ailton Quaresma Trindade Junior")
    phone = MemberPhone.objects.create(
        member=member,
        kind=MemberPhone.KIND_MOBILE,
        number="11970478945",
        is_primary=True,
        receives_sms=True,
        has_whatsapp=True,
    )

    assert phone.member == member
    assert str(phone) == f"{member.name} - 11970478945"


def test_member_fields_expose_help_texts():
    """Important member fields should expose Portuguese helper texts."""
    assert Member._meta.get_field("name").help_text == "Nome completo do membro."
    assert (
        Member._meta.get_field("marriage_date").help_text
        == "Data do casamento, quando houver."
    )
    assert (
        MemberPhone._meta.get_field("has_whatsapp").help_text
        == "Indica se este telefone possui WhatsApp."
    )
