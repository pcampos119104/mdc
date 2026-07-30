"""Tests for birthday report selectors."""

from datetime import date

import pytest

from apps.birthdays.selectors import get_birthday_members_for_period
from apps.members.models import Member


@pytest.mark.django_db
def test_get_birthday_members_filters_valid_active_members_across_year_boundary():
    """Birthday selector should filter active included members across year changes."""
    carlos = Member.objects.create(name="Carlos Lima", birth_date=date(1980, 12, 31))
    ana = Member.objects.create(name="Ana Silva", birth_date=date(1990, 1, 1))
    beatriz = Member.objects.create(name="Beatriz Alves", birth_date=date(1995, 1, 1))
    Member.objects.create(name="Inativo", birth_date=date(1990, 1, 2), is_active=False)
    Member.objects.create(
        name="Fora da lista",
        birth_date=date(1990, 1, 3),
        include_in_birthday_list=False,
    )
    Member.objects.create(name="Sem data")
    deleted_member = Member.objects.create(
        name="Removido",
        birth_date=date(1990, 12, 30),
    )
    deleted_member.delete()

    members = get_birthday_members_for_period(date(2025, 12, 29), date(2026, 1, 4))

    assert members == [carlos, ana, beatriz]
    assert [member.birthday_occurrence for member in members] == [
        date(2025, 12, 31),
        date(2026, 1, 1),
        date(2026, 1, 1),
    ]


@pytest.mark.django_db
def test_get_birthday_members_orders_by_occurrence_and_name():
    """Birthday selector should order by birthday occurrence and then by name."""
    maria = Member.objects.create(name="Maria Silva", birth_date=date(1990, 7, 22))
    ana = Member.objects.create(name="Ana Souza", birth_date=date(1990, 7, 22))
    zelia = Member.objects.create(name="Zelia Rocha", birth_date=date(1990, 7, 21))

    members = get_birthday_members_for_period(date(2026, 7, 20), date(2026, 7, 26))

    assert members == [zelia, ana, maria]
