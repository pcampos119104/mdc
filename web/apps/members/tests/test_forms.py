"""Tests for members app forms."""

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.members import forms as member_forms
from apps.members.forms import AddressForm, MemberForm
from apps.members.models import Member


pytestmark = pytest.mark.django_db


def _image_upload(name="member.gif"):
    """Return a small valid image upload for form tests."""
    return SimpleUploadedFile(
        name,
        (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
            b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00"
            b"\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        ),
        content_type="image/gif",
    )


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
            "baptism_date": "03/02/2001",
            "acclamation_date": "05/04/2020",
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


def test_member_form_renders_date_initial_values_as_brazilian_format():
    """Member form should render date initial values as dd/mm/yyyy."""
    member = Member(
        birth_date=date(1990, 1, 2),
        baptism_date=date(2001, 2, 3),
        acclamation_date=date(2020, 4, 5),
        marriage_date=date(2015, 6, 7),
    )
    form = MemberForm(instance=member)

    assert 'value="02/01/1990"' in form["birth_date"].as_widget()
    assert 'value="03/02/2001"' in form["baptism_date"].as_widget()
    assert 'value="05/04/2020"' in form["acclamation_date"].as_widget()
    assert 'value="07/06/2015"' in form["marriage_date"].as_widget()


def test_member_form_rejects_iso_date_format():
    """Member form should require dates submitted as dd/mm/yyyy."""
    form = MemberForm(
        data={
            "name": "Maria Silva",
            "registration_type": Member.RegistrationType.MEMBER,
            "birth_date": "1990-01-02",
        }
    )

    assert not form.is_valid()
    assert "birth_date" in form.errors


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


def test_member_form_rejects_oversized_photo(monkeypatch):
    """Member form should reject images above the configured upload limit."""
    monkeypatch.setattr(member_forms, "MEMBER_PHOTO_MAX_UPLOAD_SIZE", 10)
    form = MemberForm(
        data={
            "name": "Maria Silva",
            "registration_type": Member.RegistrationType.MEMBER,
        },
        files={"photo": _image_upload()},
    )

    assert not form.is_valid()
    assert "Envie uma foto de até 5 MB." in form.errors["photo"]
