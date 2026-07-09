"""Tests for members app forms."""

from datetime import date

import pytest

from apps.members.forms import AddressForm, MemberForm, PhoneForm, PhoneFormSet
from apps.members.models import Member, Phone


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
            ],
            "cpf": "123.456.789-01",
            "baptism_date": "2001-02-03",
            "acclamation_date": "2020-04-05",
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
    assert form.cleaned_data["registration_type"] == Member.RegistrationType.MEMBER
    assert form.cleaned_data["classifications"] == [
        Member.Classification.CELEBRANDO,
        Member.Classification.WOMEN,
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


def test_phone_formset_accepts_one_phone_and_one_empty_slot():
    """Phone formset should allow the second fixed phone slot to stay empty."""
    formset = PhoneFormSet(
        data={
            "phones-TOTAL_FORMS": "2",
            "phones-INITIAL_FORMS": "0",
            "phones-MIN_NUM_FORMS": "0",
            "phones-MAX_NUM_FORMS": "2",
            "phones-0-kind": Phone.KIND_MOBILE,
            "phones-0-number": "(11) 99999-9999",
            "phones-0-contact_name": "",
            "phones-0-is_primary": "on",
            "phones-0-receives_sms": "",
            "phones-0-has_whatsapp": "on",
            "phones-1-kind": "",
            "phones-1-number": "",
            "phones-1-contact_name": "",
            "phones-1-is_primary": "",
            "phones-1-receives_sms": "",
            "phones-1-has_whatsapp": "",
        },
        instance=Member(name="Maria Silva"),
    )

    assert formset.is_valid(), formset.errors
    assert len(formset.forms) == 2
    assert formset.forms[0].cleaned_data["number"] == "11999999999"
    assert formset.forms[1].cleaned_data == {}


def test_phone_formset_rejects_more_than_two_phones():
    """Phone formset should not accept more than two submitted phone records."""
    formset = PhoneFormSet(
        data={
            "phones-TOTAL_FORMS": "3",
            "phones-INITIAL_FORMS": "0",
            "phones-MIN_NUM_FORMS": "0",
            "phones-MAX_NUM_FORMS": "2",
            "phones-0-kind": Phone.KIND_MOBILE,
            "phones-0-number": "11999999999",
            "phones-1-kind": Phone.KIND_HOME,
            "phones-1-number": "1133334444",
            "phones-2-kind": Phone.KIND_WORK,
            "phones-2-number": "1144445555",
        },
        instance=Member(name="Maria Silva"),
    )

    assert not formset.is_valid()
    assert formset.non_form_errors()
