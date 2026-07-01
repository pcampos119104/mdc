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


@pytest.mark.django_db
def test_home_page_renders(client):
    """Home page should return a successful response and render its template."""
    response = client.get(reverse("home"))

    assert response.status_code == 200
    template_names = [template.name for template in response.templates if template.name]
    assert "home.html" in template_names


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
