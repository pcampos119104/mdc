"""Tests for Natal Feliz admin configuration."""

import pytest
from django.contrib.admin.sites import site
from django.urls import reverse

from apps.christmas.admin import (
    ChildAdmin,
    ChristmasEventAdmin,
    ChristmasSponsorshipAdmin,
)
from apps.christmas.models import Child, ChristmasEvent, ChristmasSponsorship


def test_child_is_registered_in_admin():
    """Child should be available in the Django admin site."""
    child_admin = site._registry[Child]

    assert isinstance(child_admin, ChildAdmin)
    assert child_admin.list_display == (
        "name",
        "mother_name",
        "contact_phone",
        "birth_date",
        "clothing_size",
    )
    assert child_admin.search_fields == ("name", "mother_name", "contact_phone")


@pytest.mark.django_db
def test_child_admin_changelist_loads(admin_client):
    """Child changelist should be accessible to an admin user."""
    response = admin_client.get(reverse("admin:christmas_child_changelist"))

    assert response.status_code == 200


def test_sponsorship_is_registered_in_admin():
    """Sponsorship should be available in the Django admin site."""
    sponsorship_admin = site._registry[ChristmasSponsorship]

    assert isinstance(sponsorship_admin, ChristmasSponsorshipAdmin)
    assert sponsorship_admin.list_display == ("child", "sponsor", "event")
    assert sponsorship_admin.list_filter == ("event",)


@pytest.mark.django_db
def test_sponsorship_admin_changelist_loads(admin_client):
    """Sponsorship changelist should be accessible to an admin user."""
    response = admin_client.get(
        reverse("admin:christmas_christmassponsorship_changelist")
    )

    assert response.status_code == 200


def test_event_is_registered_in_admin():
    """Event should be available in the Django admin site."""
    event_admin = site._registry[ChristmasEvent]

    assert isinstance(event_admin, ChristmasEventAdmin)
    assert event_admin.list_display == ("name", "event_date", "event_time")


@pytest.mark.django_db
def test_event_admin_changelist_loads(admin_client):
    """Event changelist should be accessible to an admin user."""
    response = admin_client.get(reverse("admin:christmas_christmasevent_changelist"))

    assert response.status_code == 200
