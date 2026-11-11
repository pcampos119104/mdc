"""Tests for authentication views."""

import pytest
from django.conf import settings as django_settings
from django.urls import reverse


def test_default_language_is_brazilian_portuguese():
    """Authentication messages should use Brazilian Portuguese by default."""
    assert django_settings.LANGUAGE_CODE == "pt-br"


@pytest.mark.django_db
def test_login_page_renders(client):
    """Login page should render the local account template."""
    response = client.get(reverse("account_login"))

    assert response.status_code == 200
    assert any(template.name == "account/login.html" for template in response.templates)
    assert "Entrar no sistema" in response.content.decode()


@pytest.mark.django_db
def test_login_page_renders_password_controls(client):
    """Login page should render accessible password and Caps Lock controls."""
    response = client.get(reverse("account_login"))

    content = response.content.decode()

    assert response.status_code == 200
    assert ":type=\"showPassword ? 'text' : 'password'\"" in content
    assert "Mostrar senha" in content
    assert 'aria-controls="id_password"' in content
    assert "getModifierState('CapsLock')" in content
    assert "Caps Lock está ativado" in content
    assert 'role="status"' in content


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
    assert mailoutbox[0].subject == "Redefinição de senha | Comuna Bristol"
    assert "Recebemos uma solicitação para redefinir a senha" in mailoutbox[0].body
    assert "/accounts/password/reset/key/" in mailoutbox[0].body
    assert "Sua senha continuará a mesma." in mailoutbox[0].body
    assert "Password Reset" not in mailoutbox[0].body


@pytest.mark.django_db
def test_password_reset_for_unknown_email_sends_portuguese_message(
    client, mailoutbox, settings
):
    """Unknown addresses should receive the non-enumerating Portuguese email."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    response = client.post(
        reverse("account_reset_password"), {"email": "unknown@example.com"}
    )

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("account_reset_password_done")
    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "Conta não encontrada | Comuna Bristol"
    assert "não encontramos uma conta cadastrada" in mailoutbox[0].body
    assert reverse("account_signup") in mailoutbox[0].body
    assert "Unknown Account" not in mailoutbox[0].body


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


@pytest.mark.django_db
def test_header_shows_account_actions_for_authenticated_user(
    client, django_user_model
):
    """Authenticated users should see password and logout actions in the header."""
    user = django_user_model.objects.create_user(
        username="member",
        email="member@example.com",
        password="secret-pass-123",
    )
    client.force_login(user)

    response = client.get(reverse("home"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Minha conta" in content
    assert f'href="{reverse("account_change_password")}"' in content
    assert f'href="{reverse("account_logout")}"' in content
