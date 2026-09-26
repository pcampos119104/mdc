"""Tests for Natal Feliz models."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.christmas.models import Child


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
