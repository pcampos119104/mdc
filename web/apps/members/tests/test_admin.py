"""Tests for members app admin configuration."""

import pytest
from django.contrib.admin.sites import site
from django.urls import reverse

from apps.members.models import Address, Member, Phone


def test_models_are_registered_in_admin():
    """Members models should be registered in the Django admin site."""
    assert site.is_registered(Member)
    assert site.is_registered(Address)
    assert site.is_registered(Phone)


@pytest.mark.django_db
def test_member_admin_changelist_loads(admin_client):
    """Members changelist should be accessible to an admin user."""
    response = admin_client.get(reverse("admin:members_member_changelist"))

    assert response.status_code == 200
