"""Tests for Natal Feliz models."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.christmas.models import Child, ChristmasEvent, ChristmasSponsorship
from apps.members.models import Member


@pytest.mark.django_db
def test_child_can_be_created_with_required_fields():
    """Child should persist the initial campaign registration fields."""
    child = Child.objects.create(
        name="Ana Silva",
        mother_name="Maria Silva",
        birth_date=date(2018, 5, 12),
    )

    child.full_clean()

    assert child.pk is not None
    assert child.name == "Ana Silva"
    assert child.mother_name == "Maria Silva"
    assert child.birth_date == date(2018, 5, 12)
    assert str(child) == "Ana Silva"


@pytest.mark.django_db
def test_child_requires_name_mother_name_and_birth_date():
    """Child should require all initial campaign registration fields."""
    child = Child(name="", mother_name="", birth_date=None)

    with pytest.raises(ValidationError) as exc_info:
        child.full_clean()

    assert set(exc_info.value.message_dict) == {"name", "mother_name", "birth_date"}


@pytest.mark.django_db
def test_children_are_ordered_by_name():
    """Children should use their names as the default ordering."""
    Child.objects.create(
        name="Zélia Souza",
        mother_name="Marta Souza",
        birth_date=date(2019, 1, 10),
    )
    Child.objects.create(
        name="Ana Lima",
        mother_name="Clara Lima",
        birth_date=date(2018, 2, 20),
    )

    assert list(Child.objects.values_list("name", flat=True)) == [
        "Ana Lima",
        "Zélia Souza",
    ]


def test_child_fields_expose_help_texts():
    """Child fields should expose Portuguese helper texts."""
    assert Child._meta.get_field("name").help_text == "Nome completo da criança."
    assert (
        Child._meta.get_field("mother_name").help_text
        == "Nome completo da mãe da criança."
    )
    assert (
        Child._meta.get_field("birth_date").help_text
        == "Data de nascimento da criança."
    )


@pytest.mark.django_db
def test_child_can_be_soft_deleted_restored_and_hard_deleted():
    """Child soft delete should preserve records until explicitly removed."""
    child = Child.objects.create(
        name="Ana Silva",
        mother_name="Maria Silva",
        birth_date=date(2018, 5, 12),
    )
    child_pk = child.pk

    deleted_count, deleted_by_model = child.delete()

    assert deleted_count == 1
    assert deleted_by_model == {"christmas.Child": 1}
    assert not Child.objects.filter(pk=child_pk).exists()

    deleted_child = Child.all_objects.get(pk=child_pk)
    assert deleted_child.deleted_at is not None

    restored_count, restored_by_model = deleted_child.restore()

    assert restored_count == 1
    assert restored_by_model == {"christmas.Child": 1}
    restored_child = Child.objects.get(pk=child_pk)
    restored_child.hard_delete()
    assert not Child.all_objects.filter(pk=child_pk).exists()


@pytest.mark.django_db
def test_event_persists_required_schedule_data():
    """Event should persist its name, date, time, and readable representation."""
    event = ChristmasEvent.objects.create(
        name="Natal Feliz 2026",
        event_date=date(2026, 12, 20),
        event_time="14:30",
    )

    event.full_clean()

    assert event.pk is not None
    assert event.name == "Natal Feliz 2026"
    assert event.event_date == date(2026, 12, 20)
    assert str(event) == "Natal Feliz 2026"


@pytest.mark.django_db
def test_event_requires_name_date_and_time():
    """Event should require all scheduling fields."""
    event = ChristmasEvent(name="", event_date=None, event_time=None)

    with pytest.raises(ValidationError) as exc_info:
        event.full_clean()

    assert set(exc_info.value.message_dict) == {"name", "event_date", "event_time"}


@pytest.mark.django_db
def test_sponsorship_relates_event_sponsor_and_child():
    """Sponsorship should persist its event, member, child, and readable name."""
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

    sponsorship = ChristmasSponsorship.objects.create(
        event=event,
        sponsor=sponsor,
        child=child,
    )

    assert sponsorship in event.sponsorships.all()
    assert sponsorship in sponsor.christmas_sponsorships.all()
    assert sponsorship in child.christmas_sponsorships.all()
    assert str(sponsorship) == "Ana Silva — João Santos (Natal Feliz 2026)"


@pytest.mark.django_db
def test_child_has_only_one_sponsor_per_event_but_can_join_another_event():
    """A child should have at most one sponsor in each event."""
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

    with pytest.raises(IntegrityError), transaction.atomic():
        ChristmasSponsorship.objects.create(
            event=first_event,
            sponsor=second_sponsor,
            child=child,
        )

    other_event_sponsorship = ChristmasSponsorship.objects.create(
        event=second_event,
        sponsor=second_sponsor,
        child=child,
    )
    assert other_event_sponsorship.pk is not None


@pytest.mark.django_db
def test_deleting_event_cascades_sponsorship_only():
    """Deleting an event should preserve its child and sponsor records."""
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
    sponsorship = ChristmasSponsorship.objects.create(
        event=event,
        sponsor=sponsor,
        child=child,
    )

    event.delete()

    assert not ChristmasSponsorship.objects.filter(pk=sponsorship.pk).exists()
    assert Member.objects.filter(pk=sponsor.pk).exists()
    assert Child.objects.filter(pk=child.pk).exists()
