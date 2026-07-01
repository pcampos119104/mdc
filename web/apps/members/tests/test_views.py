"""Tests for members app views."""

import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.shortcuts import render as django_render
from django.urls import reverse

from apps.members import views as member_views
from apps.members.models import Address, Member, Phone


def _create_user(django_user_model):
    """Create a user allowed to access member management views."""
    return django_user_model.objects.create_user(
        username="leader",
        email="leader@example.com",
        password="secret-pass-123",
    )


def _member_post_data(**overrides):
    """Build member POST data, including address and phone formset fields."""
    data = {
        "name": "Maria Silva",
        "registration_type": "Membro",
        "person_type": "Pessoa",
        "member_type": "Membro ativo",
        "cpf": "123.456.789-00",
        "birth_date": "1990-01-02",
        "sex": Member.Sex.FEMALE,
        "nationality": "Brasil",
        "birthplace": "Sao Paulo SP",
        "email": "maria@example.com",
        "father_name": "Jose Silva",
        "mother_name": "Ana Silva",
        "spouse_name": "",
        "marital_status": Member.MaritalStatus.SINGLE,
        "marriage_date": "",
        "is_active": "on",
        "postal_code": "01001-000",
        "country": "Brasil",
        "state": "SP",
        "city": "Sao Paulo",
        "street": "Rua Central",
        "street_number": "123",
        "complement": "Casa",
        "district": "Centro",
        "phones-TOTAL_FORMS": "2",
        "phones-INITIAL_FORMS": "0",
        "phones-MIN_NUM_FORMS": "0",
        "phones-MAX_NUM_FORMS": "2",
        "phones-0-kind": Phone.KIND_MOBILE,
        "phones-0-number": "11999999999",
        "phones-0-contact_name": "",
        "phones-0-is_primary": "on",
        "phones-0-receives_sms": "on",
        "phones-0-has_whatsapp": "on",
        "phones-1-kind": "",
        "phones-1-number": "",
        "phones-1-contact_name": "",
        "phones-1-is_primary": "",
        "phones-1-receives_sms": "",
        "phones-1-has_whatsapp": "",
    }
    data.update(overrides)
    return data


def _attach_request_state(request, user):
    """Attach user, session and message storage to a request factory request."""
    SessionMiddleware(lambda request: None).process_request(request)
    request._messages = FallbackStorage(request)
    request.user = user
    return request


def _record_rendered_templates(monkeypatch):
    """Record template names rendered by members views during direct view tests."""
    template_names = []

    def recording_render(request, template_name, context=None, *args, **kwargs):
        """Store the template name and delegate to Django's render helper."""
        template_names.append(template_name)
        return django_render(request, template_name, context, *args, **kwargs)

    monkeypatch.setattr(member_views, "render", recording_render)
    return template_names


@pytest.mark.django_db
def test_member_views_require_authentication(client):
    """Anonymous users should be redirected away from member management views."""
    member = Member.objects.create(name="Maria Silva")
    urls = [
        reverse("members:list"),
        reverse("members:create"),
        reverse("members:update", args=[member.pk]),
        reverse("members:remove", args=[member.pk]),
    ]

    for url in urls:
        response = client.get(url)

        assert response.status_code == 302
        assert response.headers["Location"].startswith(reverse("account_login"))


@pytest.mark.django_db
def test_member_list_renders_and_filters_by_search(rf, django_user_model, monkeypatch):
    """Members list should render and filter by member contact data."""
    user = _create_user(django_user_model)
    matching_member = Member.objects.create(
        name="Maria Silva",
        email="maria@example.com",
        cpf="12345678900",
    )
    other_member = Member.objects.create(name="Joao Souza", email="joao@example.com")
    Address.objects.create(member=matching_member, city="Sao Paulo", district="Centro")
    Phone.objects.create(
        member=matching_member,
        kind=Phone.KIND_MOBILE,
        number="11999999999",
    )
    template_names = _record_rendered_templates(monkeypatch)
    request = _attach_request_state(
        rf.get(reverse("members:list"), {"q": "(11) 9999"}),
        user,
    )

    response = member_views.member_list(request)

    assert response.status_code == 200
    assert template_names == ["members/member_list.html"]
    assert matching_member.name.encode() in response.content
    assert other_member.name.encode() not in response.content


@pytest.mark.django_db
def test_member_create_page_renders_for_authenticated_user(
    rf,
    django_user_model,
    monkeypatch,
):
    """Authenticated users should be able to access the member creation form."""
    user = _create_user(django_user_model)
    template_names = _record_rendered_templates(monkeypatch)
    request = _attach_request_state(rf.get(reverse("members:create")), user)

    response = member_views.MemberCreateView.as_view()(request)

    assert response.status_code == 200
    assert template_names == ["members/member_form.html"]


@pytest.mark.django_db
def test_member_create_saves_member_address_and_phone(client, django_user_model):
    """Valid member submission should create member, address and phone records."""
    user = _create_user(django_user_model)
    client.force_login(user)

    response = client.post(reverse("members:create"), _member_post_data())

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("members:list")
    member = Member.objects.get(name="Maria Silva")
    assert member.cpf == "12345678900"
    assert member.address.city == "Sao Paulo"
    assert member.address.postal_code == "01001000"
    phone = member.phones.get()
    assert phone.number == "11999999999"
    assert phone.is_primary is True
    assert phone.has_whatsapp is True


@pytest.mark.django_db
def test_member_create_rejects_more_than_two_phones(client, django_user_model):
    """Member creation should reject submissions with more than two phones."""
    user = _create_user(django_user_model)
    client.force_login(user)
    data = _member_post_data(
        **{
            "phones-TOTAL_FORMS": "3",
            "phones-2-kind": Phone.KIND_WORK,
            "phones-2-number": "1144445555",
            "phones-2-contact_name": "",
            "phones-2-is_primary": "",
            "phones-2-receives_sms": "",
            "phones-2-has_whatsapp": "",
        }
    )

    response = client.post(reverse("members:create"), data)

    assert response.status_code == 200
    assert Member.objects.count() == 0


@pytest.mark.django_db
def test_member_create_rejects_invalid_submission(rf, django_user_model, monkeypatch):
    """Invalid member submission should re-render the form without saving."""
    user = _create_user(django_user_model)
    template_names = _record_rendered_templates(monkeypatch)
    request = _attach_request_state(
        rf.post(reverse("members:create"), _member_post_data(name="")),
        user,
    )

    response = member_views.MemberCreateView.as_view()(request)

    assert response.status_code == 200
    assert template_names == ["members/member_form.html"]
    assert Member.objects.count() == 0


@pytest.mark.django_db
def test_member_update_page_renders_for_authenticated_user(
    rf,
    django_user_model,
    monkeypatch,
):
    """Authenticated users should be able to access the member update form."""
    user = _create_user(django_user_model)
    member = Member.objects.create(name="Maria Silva")
    template_names = _record_rendered_templates(monkeypatch)
    request = _attach_request_state(
        rf.get(reverse("members:update", args=[member.pk])),
        user,
    )

    response = member_views.MemberUpdateView.as_view()(request, pk=member.pk)

    assert response.status_code == 200
    assert template_names == ["members/member_form.html"]


@pytest.mark.django_db
def test_member_update_saves_member_address_and_phone(client, django_user_model):
    """Valid member update should persist member, address and phone changes."""
    user = _create_user(django_user_model)
    client.force_login(user)
    member = Member.objects.create(name="Maria Silva")
    address = Address.objects.create(member=member, city="Sao Paulo")
    phone = Phone.objects.create(
        member=member,
        kind=Phone.KIND_MOBILE,
        number="11999999999",
    )
    data = _member_post_data(
        name="Maria Silva Atualizada",
        city="Santos",
        **{
            "phones-INITIAL_FORMS": "1",
            "phones-0-id": str(phone.pk),
            "phones-0-kind": Phone.KIND_HOME,
            "phones-0-number": "1133334444",
            "phones-0-has_whatsapp": "",
        },
    )

    response = client.post(reverse("members:update", args=[member.pk]), data)

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("members:list")
    member.refresh_from_db()
    address.refresh_from_db()
    phone.refresh_from_db()
    assert member.name == "Maria Silva Atualizada"
    assert address.city == "Santos"
    assert phone.kind == Phone.KIND_HOME
    assert phone.number == "1133334444"
    assert phone.has_whatsapp is False


@pytest.mark.django_db
def test_member_update_rejects_invalid_submission(rf, django_user_model, monkeypatch):
    """Invalid member update should re-render the form without saving changes."""
    user = _create_user(django_user_model)
    member = Member.objects.create(name="Maria Silva")
    template_names = _record_rendered_templates(monkeypatch)
    request = _attach_request_state(
        rf.post(reverse("members:update", args=[member.pk]), _member_post_data(name="")),
        user,
    )

    response = member_views.MemberUpdateView.as_view()(request, pk=member.pk)

    assert response.status_code == 200
    assert template_names == ["members/member_form.html"]
    member.refresh_from_db()
    assert member.name == "Maria Silva"


@pytest.mark.django_db
def test_member_remove_page_renders_for_authenticated_user(
    rf,
    django_user_model,
    monkeypatch,
):
    """Authenticated users should be able to access the member removal page."""
    user = _create_user(django_user_model)
    member = Member.objects.create(name="Maria Silva")
    template_names = _record_rendered_templates(monkeypatch)
    request = _attach_request_state(
        rf.get(reverse("members:remove", args=[member.pk])),
        user,
    )

    response = member_views.MemberRemoveView.as_view()(request, pk=member.pk)

    assert response.status_code == 200
    assert template_names == ["members/member_confirm_remove.html"]


@pytest.mark.django_db
def test_member_remove_soft_deletes_member_and_keeps_contact_records(
    client,
    django_user_model,
):
    """Confirmed removal should soft delete the member and keep contact records."""
    user = _create_user(django_user_model)
    client.force_login(user)
    member = Member.objects.create(name="Maria Silva")
    address = Address.objects.create(member=member, city="Sao Paulo")
    phone = Phone.objects.create(
        member=member,
        kind=Phone.KIND_MOBILE,
        number="11999999999",
    )

    response = client.post(reverse("members:remove", args=[member.pk]))

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("members:list")
    assert not Member.objects.filter(pk=member.pk).exists()

    deleted_member = Member.all_objects.get(pk=member.pk)
    assert deleted_member.deleted_at is not None
    assert Address.objects.filter(pk=address.pk).exists()
    assert Phone.objects.filter(pk=phone.pk).exists()
