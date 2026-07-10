"""Tests for members app admin configuration."""

import pytest
from django.contrib.admin.sites import site
from django.urls import reverse

from apps.members.models import Address, Member, Phone
from apps.members.admin import MemberAdmin


def test_models_are_registered_in_admin():
    """Members models should be registered in the Django admin site."""
    assert site.is_registered(Member)
    assert site.is_registered(Address)
    assert site.is_registered(Phone)


def test_member_admin_exposes_birthday_list_field():
    """Member admin should expose relevant quick management fields."""
    member_admin = site._registry[Member]

    assert isinstance(member_admin, MemberAdmin)
    assert "person_type" not in member_admin.list_display
    assert "registration_type" in member_admin.list_display
    assert "classifications_display" in member_admin.list_display
    assert "profession" in member_admin.list_display
    assert "baptism_date" in member_admin.list_display
    assert "acclamation_date" in member_admin.list_display
    assert "include_in_birthday_list" in member_admin.list_display
    assert "registration_type" in member_admin.list_filter
    assert "include_in_birthday_list" in member_admin.list_filter
    assert "profession" in member_admin.search_fields


@pytest.mark.django_db
def test_member_admin_changelist_loads(admin_client):
    """Members changelist should be accessible to an admin user."""
    response = admin_client.get(reverse("admin:members_member_changelist"))

    assert response.status_code == 200
