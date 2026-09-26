"""Tests for Natal Feliz admin configuration."""

import pytest
from django.contrib.admin.sites import site
from django.urls import reverse

from apps.christmas.admin import ChildAdmin
from apps.christmas.models import Child


def test_child_is_registered_in_admin():
    """Child should be available in the Django admin site."""
    child_admin = site._registry[Child]

    assert isinstance(child_admin, ChildAdmin)
    assert child_admin.list_display == ("name", "mother_name", "birth_date")
    assert child_admin.search_fields == ("name", "mother_name")


@pytest.mark.django_db
def test_child_admin_changelist_loads(admin_client):
    """Child changelist should be accessible to an admin user."""
    response = admin_client.get(reverse("admin:christmas_child_changelist"))

    assert response.status_code == 200
