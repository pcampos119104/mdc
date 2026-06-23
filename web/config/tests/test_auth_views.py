"""Tests for authentication views."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_login_page_renders(client):
    """Login page should render the local account template."""
    response = client.get(reverse("account_login"))

    assert response.status_code == 200
    assert any(template.name == "account/login.html" for template in response.templates)
    assert "Entrar no sistema" in response.content.decode()


@pytest.mark.django_db
def test_login_accepts_email(client, django_user_model):
    """Users should be able to authenticate with their email address."""
    password = "secret-pass-123"
    user = django_user_model.objects.create_user(
        username="admin",
        email="admin@example.com",
        password=password,
    )

    response = client.post(
        reverse("account_login"),
        {"login": user.email, "password": password},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert str(user.pk) == client.session.get("_auth_user_id")


@pytest.mark.django_db
def test_logout_page_renders_for_authenticated_user(client, django_user_model):
    """Logout confirmation page should render for signed-in users."""
    user = django_user_model.objects.create_user(
        username="member",
        email="member@example.com",
        password="secret-pass-123",
    )
    client.force_login(user)

    response = client.get(reverse("account_logout"))

    assert response.status_code == 200
    assert any(template.name == "account/logout.html" for template in response.templates)


@pytest.mark.django_db
def test_password_reset_page_renders(client):
    """Password reset page should render the local account template."""
    response = client.get(reverse("account_reset_password"))

    assert response.status_code == 200
    assert any(
        template.name == "account/password_reset.html" for template in response.templates
    )


@pytest.mark.django_db
def test_password_reset_submission_redirects_and_sends_email(
    client, django_user_model, mailoutbox, settings
):
    """Submitting password reset should redirect to the done page and send mail."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = django_user_model.objects.create_user(
        username="member",
        email="member@example.com",
        password="secret-pass-123",
    )

    response = client.post(reverse("account_reset_password"), {"email": user.email})

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("account_reset_password_done")
    assert len(mailoutbox) == 1
    assert user.email in mailoutbox[0].to


@pytest.mark.django_db
def test_password_change_requires_authentication(client):
    """Anonymous users should be redirected to the login page."""
    response = client.get(reverse("account_change_password"))

    assert response.status_code == 302
    assert response.headers["Location"].startswith(reverse("account_login"))


@pytest.mark.django_db
def test_password_change_page_renders_for_authenticated_user(client, django_user_model):
    """Authenticated users should be able to access password change."""
    user = django_user_model.objects.create_user(
        username="member",
        email="member@example.com",
        password="secret-pass-123",
    )
    client.force_login(user)

    response = client.get(reverse("account_change_password"))

    assert response.status_code == 200
    assert any(
        template.name == "account/password_change.html" for template in response.templates
    )
