"""Tests for Natal Feliz forms."""

from datetime import date

import pytest

from apps.christmas.forms import (
    ChildForm,
    ChristmasEventForm,
    ChristmasSponsorshipForm,
)
from apps.christmas.models import Child, ChristmasEvent, ChristmasSponsorship
from apps.members.models import Member


@pytest.mark.django_db
def test_child_form_accepts_brazilian_date_and_saves_child():
    """Child form should parse Brazilian dates and create a child."""
    form = ChildForm(
        data={
            "name": "Ana Silva",
            "mother_name": "Maria Silva",
            "birth_date": "12/05/2018",
            "clothing_size": "8",
        }
    )

    assert form.is_valid(), form.errors
    child = form.save()
    assert child.birth_date == date(2018, 5, 12)
    assert child.clothing_size == 8


def test_christmas_forms_configure_date_mask_widgets():
    """Christmas date widgets should expose the client-side mask settings."""
    child_form = ChildForm()
    event_form = ChristmasEventForm()

    assert child_form.fields["birth_date"].widget.attrs["date_mask"] is True
    assert child_form.fields["birth_date"].widget.attrs["maxlength"] == "10"
    assert event_form.fields["event_date"].widget.attrs["date_mask"] is True
    assert event_form.fields["event_date"].widget.attrs["maxlength"] == "10"


def test_child_form_requires_all_fields_with_portuguese_messages():
    """Child form should report required fields in Portuguese."""
    form = ChildForm(data={})

    assert not form.is_valid()
    assert form.errors["name"] == ["Informe o nome da criança."]
    assert form.errors["mother_name"] == ["Informe o nome da mãe."]
    assert form.errors["birth_date"] == ["Informe a data de nascimento."]
    assert form.errors["clothing_size"] == ["Informe o tamanho da roupa."]


def test_child_form_rejects_invalid_birth_date():
    """Child form should reject malformed birth dates in Portuguese."""
    form = ChildForm(
        data={
            "name": "Ana Silva",
            "mother_name": "Maria Silva",
            "birth_date": "31/02/2018",
            "clothing_size": "8",
        }
    )

    assert not form.is_valid()
    assert form.errors["birth_date"] == [
        "Informe uma data válida no formato dd/mm/aaaa."
    ]


def test_child_form_rejects_non_numeric_clothing_size():
    """Child form should accept only numeric clothing sizes."""
    form = ChildForm(
        data={
            "name": "Ana Silva",
            "mother_name": "Maria Silva",
            "birth_date": "12/05/2018",
            "clothing_size": "P",
        }
    )

    assert not form.is_valid()
    assert form.errors["clothing_size"] == ["Informe um tamanho de roupa válido."]


@pytest.mark.django_db
def test_event_form_accepts_brazilian_date_and_time():
    """Event form should parse and save Brazilian schedule values."""
    form = ChristmasEventForm(
        data={
            "name": "Natal Feliz 2026",
            "event_date": "20/12/2026",
            "event_time": "14:30",
            "label_note": "Entregar o presente sem embalagem.",
        }
    )

    assert form.is_valid(), form.errors
    event = form.save()
    assert event.event_date == date(2026, 12, 20)
    assert event.event_time.strftime("%H:%M") == "14:30"
    assert event.label_note == "Entregar o presente sem embalagem."


def test_event_form_requires_all_fields_with_portuguese_messages():
    """Event form should report required fields in Portuguese."""
    form = ChristmasEventForm(data={})

    assert not form.is_valid()
    assert form.errors["name"] == ["Informe o nome do evento."]
    assert form.errors["event_date"] == ["Informe a data do evento."]
    assert form.errors["event_time"] == ["Informe o horário do evento."]


def test_event_form_rejects_label_note_longer_than_100_characters():
    """Event form should enforce the printable note length in Portuguese."""
    form = ChristmasEventForm(
        data={
            "name": "Natal Feliz 2026",
            "event_date": "20/12/2026",
            "event_time": "14:30",
            "label_note": "a" * 101,
        }
    )

    assert not form.is_valid()
    assert form.errors["label_note"] == [
        "A observação deve ter no máximo 100 caracteres."
    ]


@pytest.mark.django_db
def test_sponsorship_form_saves_valid_relationship():
    """Sponsorship form should create a relationship for the selected event."""
    event = ChristmasEvent.objects.create(
        name="Natal Feliz 2026",
        event_date=date(2026, 12, 20),
        event_time="14:30",
    )
    sponsor = Member.objects.create(name="João Santos")
    child = Child.objects.create(
        name="Ana Silva",
        mother_name="Maria Silva",
        birth_date=date(2018, 5, 12),
    )
    form = ChristmasSponsorshipForm(
        data={"sponsor": sponsor.pk, "child": child.pk},
        event=event,
    )

    assert form.is_valid(), form.errors
    sponsorship = form.save()
    assert sponsorship.sponsor == sponsor
    assert sponsorship.child == child
    assert sponsorship.event == event


@pytest.mark.django_db
def test_sponsorship_form_lists_only_active_church_members():
    """Sponsor choices should exclude inactive, non-member, and removed records."""
    active_member = Member.objects.create(name="Ativo")
    Member.objects.create(name="Inativo", is_active=False, inactive_reason="Mudança")
    Member.objects.create(name="Visitante", is_church_member=False)
    removed_member = Member.objects.create(name="Removido")
    removed_member.delete()

    event = ChristmasEvent.objects.create(
        name="Natal Feliz 2026",
        event_date=date(2026, 12, 20),
        event_time="14:30",
    )
    form = ChristmasSponsorshipForm(event=event)

    assert list(form.fields["sponsor"].queryset) == [active_member]


@pytest.mark.django_db
def test_sponsorship_form_rejects_second_sponsor_for_child_in_same_event():
    """Sponsorship form should explain the child and event uniqueness rule."""
    event = ChristmasEvent.objects.create(
        name="Natal Feliz 2026",
        event_date=date(2026, 12, 20),
        event_time="14:30",
    )
    first_sponsor = Member.objects.create(name="João Santos")
    second_sponsor = Member.objects.create(name="Paulo Lima")
    child = Child.objects.create(
        name="Ana Silva",
        mother_name="Maria Silva",
        birth_date=date(2018, 5, 12),
    )
    ChristmasSponsorship.objects.create(
        event=event,
        sponsor=first_sponsor,
        child=child,
    )

    form = ChristmasSponsorshipForm(
        data={"sponsor": second_sponsor.pk, "child": child.pk},
        event=event,
    )

    assert not form.is_valid()
    assert form.errors["child"] == [
        "Esta criança já possui um padrinho neste evento."
    ]


@pytest.mark.django_db
def test_sponsorship_form_allows_same_child_in_another_event():
    """Sponsorship form should allow a child to join another event."""
    first_event = ChristmasEvent.objects.create(
        name="Primeiro evento",
        event_date=date(2026, 12, 20),
        event_time="14:30",
    )
    second_event = ChristmasEvent.objects.create(
        name="Segundo evento",
        event_date=date(2027, 12, 20),
        event_time="14:30",
    )
    first_sponsor = Member.objects.create(name="João Santos")
    second_sponsor = Member.objects.create(name="Paulo Lima")
    child = Child.objects.create(
        name="Ana Silva",
        mother_name="Maria Silva",
        birth_date=date(2018, 5, 12),
    )
    ChristmasSponsorship.objects.create(
        event=first_event,
        sponsor=first_sponsor,
        child=child,
    )

    form = ChristmasSponsorshipForm(
        data={"sponsor": second_sponsor.pk, "child": child.pk},
        event=second_event,
    )

    assert form.is_valid(), form.errors
