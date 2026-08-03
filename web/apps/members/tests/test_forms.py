"""Tests for members app forms."""

from datetime import date

import pytest

from apps.members.forms import AddressForm, MemberForm
from apps.members.models import Member


pytestmark = pytest.mark.django_db


def test_member_form_normalizes_masked_cpf():
    """Member form should accept masked CPF and store only digits."""
    form = MemberForm(
        data={
            "name": "Maria Silva",
            "registration_type": Member.RegistrationType.MEMBER,
            "classifications": [
                Member.Classification.CELEBRANDO,
                Member.Classification.WOMEN,
                Member.Classification.VOLUNTEER,
            ],
            "cpf": "123.456.789-01",
            "baptism_date": "2001-02-03",
            "acclamation_date": "2020-04-05",
            "profession": "Professora",
            "phone": "(11) 99999-9999",
            "sex": Member.Sex.FEMALE,
            "marital_status": Member.MaritalStatus.SINGLE,
            "include_in_birthday_list": "on",
            "is_active": "on",
        }
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["cpf"] == "12345678901"
    assert form.cleaned_data["baptism_date"] == date(2001, 2, 3)
    assert form.cleaned_data["acclamation_date"] == date(2020, 4, 5)
    assert form.cleaned_data["include_in_birthday_list"] is True
    assert form.cleaned_data["profession"] == "Professora"
    assert form.cleaned_data["phone"] == "11999999999"
    assert form.cleaned_data["registration_type"] == Member.RegistrationType.MEMBER
    assert form.cleaned_data["classifications"] == [
        Member.Classification.CELEBRANDO,
        Member.Classification.WOMEN,
        Member.Classification.VOLUNTEER,
    ]


def test_member_form_requires_registration_type():
    """Member form should require the registration type."""
    form = MemberForm(data={"name": "Maria Silva", "registration_type": ""})

    assert not form.is_valid()
    assert "registration_type" in form.errors


def test_member_form_requires_reason_when_inactive():
    """Member form should require a reason when the member is inactive."""
    form = MemberForm(
        data={
            "name": "Maria Silva",
            "include_in_birthday_list": "on",
            "is_active": "",
            "inactive_reason": "",
        }
    )

    assert not form.is_valid()
    assert "inactive_reason" in form.errors


def test_address_form_normalizes_postal_code_and_state():
    """Address form should normalize CEP and Brazilian state abbreviation."""
    form = AddressForm(data={"postal_code": "01001-000", "state": "sp"})

    assert form.is_valid(), form.errors
    assert form.cleaned_data["postal_code"] == "01001000"
    assert form.cleaned_data["state"] == "SP"


def test_member_form_rejects_invalid_phone():
    """Member form should reject malformed phone values."""
    form = MemberForm(
        data={
            "name": "Maria Silva",
            "registration_type": Member.RegistrationType.MEMBER,
            "phone": "abc",
        }
    )

    assert not form.is_valid()
    assert "phone" in form.errors
