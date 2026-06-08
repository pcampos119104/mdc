"""Tests for project-level views."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_page_renders(client):
    """Home page should return a successful response and render its template."""
    response = client.get(reverse("home"))

    assert response.status_code == 200
    template_names = [template.name for template in response.templates if template.name]
    assert "home.html" in template_names
