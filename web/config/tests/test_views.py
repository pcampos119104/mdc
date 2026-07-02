"""Tests for project-level views."""

import importlib

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import Resolver404, clear_url_caches, resolve, reverse

from config import urls, views


def reload_project_urls():
    """Reload project URL patterns after changing URL-related settings."""
    clear_url_caches()
    importlib.reload(urls)


def _create_user(django_user_model):
    """Create a user allowed to access the system home page."""
    return django_user_model.objects.create_user(
        username="leader",
        email="leader@example.com",
        password="secret-pass-123",
    )


def test_home_page_requires_authentication(client):
    """Anonymous users should be redirected to login from the home page."""
    response = client.get(reverse("home"))

    assert response.status_code == 302
    assert response.headers["Location"].startswith(reverse("account_login"))


@pytest.mark.django_db
def test_home_page_renders_member_list(client, django_user_model):
    """Home page should display the member list for authenticated users."""
    user = _create_user(django_user_model)
    client.force_login(user)

    response = client.get(reverse("home"))

    assert response.status_code == 200
    template_names = [template.name for template in response.templates if template.name]
    assert "members/member_list.html" in template_names


def test_sentry_debug_view_raises_error(rf):
    """Sentry debug view should raise an error for manual verification."""
    request = rf.get("/sentry-debug/")

    with pytest.raises(ZeroDivisionError):
        views.sentry_debug(request)


def test_sentry_debug_url_is_available_in_debug():
    """Sentry debug URL should be available when DEBUG is enabled."""
    original_debug = settings.DEBUG

    try:
        with override_settings(DEBUG=True):
            reload_project_urls()
            match = resolve("/sentry-debug/")
            assert match.func == views.sentry_debug
    finally:
        with override_settings(DEBUG=original_debug):
            reload_project_urls()


def test_sentry_debug_url_is_not_available_outside_debug():
    """Sentry debug URL should not be available when DEBUG is disabled."""
    original_debug = settings.DEBUG

    try:
        with override_settings(DEBUG=False):
            reload_project_urls()
            with pytest.raises(Resolver404):
                resolve("/sentry-debug/")
    finally:
        with override_settings(DEBUG=original_debug):
            reload_project_urls()
