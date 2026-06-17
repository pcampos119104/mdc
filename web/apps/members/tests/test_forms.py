"""Tests for members app forms."""

import pytest

from apps.members.forms import AddressForm, MemberForm, PhoneForm
from apps.members.models import Member, Phone


pytestmark = pytest.mark.django_db


def test_member_form_normalizes_masked_cpf():
    """Member form should accept masked CPF and store only digits."""
    form = MemberForm(
        data={
            "name": "Maria Silva",
            "cpf": "123.456.789-01",
            "sex": Member.Sex.FEMALE,
            "marital_status": Member.MaritalStatus.SINGLE,
            "is_active": "on",
        }
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["cpf"] == "12345678901"


def test_address_form_normalizes_postal_code_and_state():
    """Address form should normalize CEP and Brazilian state abbreviation."""
    form = AddressForm(data={"postal_code": "01001-000", "state": "sp"})

    assert form.is_valid(), form.errors
    assert form.cleaned_data["postal_code"] == "01001000"
    assert form.cleaned_data["state"] == "SP"


def test_phone_form_normalizes_masked_number():
    """Phone form should accept masked numbers and store only digits."""
    form = PhoneForm(
        data={
            "kind": Phone.KIND_MOBILE,
            "number": "(11) 99999-9999",
            "is_primary": "on",
        }
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["number"] == "11999999999"
