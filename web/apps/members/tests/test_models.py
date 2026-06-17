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
        Member._meta.get_field("marriage_date").help_text
        == "Data do casamento, quando houver."
    )
    assert (
        MemberPhone._meta.get_field("has_whatsapp").help_text
        == "Indica se este telefone possui WhatsApp."
    )
