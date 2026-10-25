"""Tests for Natal Feliz views."""

from datetime import date

import pytest
from django.urls import reverse

from apps.christmas.models import Child, ChristmasEvent, ChristmasSponsorship
from apps.members.models import Member


def _create_user(django_user_model, *, is_staff=False):
    """Create a user for Natal Feliz view tests."""
    return django_user_model.objects.create_user(
        username="staff" if is_staff else "member",
        email="staff@example.com" if is_staff else "member@example.com",
        password="secret-pass-123",
        is_staff=is_staff,
    )


def _create_child(**overrides):
    """Create a child with valid default campaign data."""
    data = {
        "name": "Ana Silva",
        "mother_name": "Maria Silva",
        "birth_date": date(2018, 5, 12),
        "clothing_size": 8,
    }
    data.update(overrides)
    return Child.objects.create(**data)


def _create_member(**overrides):
    """Create an active church member with valid default data."""
    data = {"name": "João Santos"}
    data.update(overrides)
    return Member.objects.create(**data)


def _create_external_sponsor(**overrides):
    """Create an active external sponsor registered only for Natal Feliz."""
    data = {
        "name": "Padrinho Externo",
        "registration_type": Member.RegistrationType.CHRISTMAS,
    }
    data.update(overrides)
    return Member.objects.create(**data)


def _create_event(**overrides):
    """Create an event with valid default schedule data."""
    data = {
        "name": "Natal Feliz 2026",
        "event_date": date(2026, 12, 20),
        "event_time": "14:30",
    }
    data.update(overrides)
    return ChristmasEvent.objects.create(**data)


def _create_sponsorship(**overrides):
    """Create a sponsorship with valid default campaign data."""
    data = {
        "event": _create_event(),
        "sponsor": _create_member(),
        "child": _create_child(),
    }
    data.update(overrides)
    return ChristmasSponsorship.objects.create(**data)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route_name",
    ["child_detail", "child_update", "child_remove"],
)
def test_child_management_views_require_staff_access(
    client,
    django_user_model,
    route_name,
):
    """Only staff users should access child-specific management views."""
    child = _create_child()
    url = reverse(f"christmas:{route_name}", args=[child.pk])

    anonymous_response = client.get(url)
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(reverse("account_login"))

    user = _create_user(django_user_model)
    client.force_login(user)
    assert client.get(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("route_name", ["child_list", "child_create"])
def test_child_collection_views_require_staff_access(
    client,
    django_user_model,
    route_name,
):
    """Only staff users should access child collection management views."""
    url = reverse(f"christmas:{route_name}")

    anonymous_response = client.get(url)
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(reverse("account_login"))

    user = _create_user(django_user_model)
    client.force_login(user)
    assert client.get(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("route_name", ["event_list", "event_create"])
def test_event_collection_views_require_staff_access(
    client,
    django_user_model,
    route_name,
):
    """Only staff users should access event collection views."""
    url = reverse(f"christmas:{route_name}")

    anonymous_response = client.get(url)
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(reverse("account_login"))

    user = _create_user(django_user_model)
    client.force_login(user)
    assert client.get(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route_name",
    ["event_detail", "event_update", "event_remove"],
)
def test_event_management_views_require_staff_access(
    client,
    django_user_model,
    route_name,
):
    """Only staff users should access event-specific views."""
    event = _create_event()
    url = reverse(f"christmas:{route_name}", args=[event.pk])

    anonymous_response = client.get(url)
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(reverse("account_login"))

    user = _create_user(django_user_model)
    client.force_login(user)
    assert client.get(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route_name",
    ["sponsorship_list", "sponsorship_create"],
)
def test_sponsorship_collection_views_require_staff_access(
    client,
    django_user_model,
    route_name,
):
    """Only staff users should access event sponsorship collection views."""
    event = _create_event()
    url = reverse(f"christmas:{route_name}", args=[event.pk])

    anonymous_response = client.get(url)
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(reverse("account_login"))

    user = _create_user(django_user_model)
    client.force_login(user)
    assert client.get(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("route_name", ["sponsor_list", "sponsor_create"])
def test_sponsor_collection_views_require_staff_access(
    client,
    django_user_model,
    route_name,
):
    """Only staff users should access external sponsor collection views."""
    url = reverse(f"christmas:{route_name}")

    anonymous_response = client.get(url)
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(reverse("account_login"))

    user = _create_user(django_user_model)
    client.force_login(user)
    assert client.get(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("route_name", ["sponsor_update", "sponsor_remove"])
def test_sponsor_record_views_require_staff_access(
    client,
    django_user_model,
    route_name,
):
    """Only staff users should access external sponsor record views."""
    sponsor = _create_external_sponsor()
    url = reverse(f"christmas:{route_name}", args=[sponsor.pk])

    anonymous_response = client.get(url)
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(reverse("account_login"))

    user = _create_user(django_user_model)
    client.force_login(user)
    assert client.get(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route_name",
    ["sponsorship_detail", "sponsorship_update", "sponsorship_remove"],
)
def test_sponsorship_management_views_require_staff_access(
    client,
    django_user_model,
    route_name,
):
    """Only staff users should access event sponsorship-specific views."""
    sponsorship = _create_sponsorship()
    url = reverse(
        f"christmas:{route_name}",
        args=[sponsorship.event_id, sponsorship.pk],
    )

    anonymous_response = client.get(url)
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(reverse("account_login"))

    user = _create_user(django_user_model)
    client.force_login(user)
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_event_list_renders_searches_and_paginates(client, django_user_model):
    """Campaign root should list events and filter them by name."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    matching = _create_event(name="Natal Especial")
    _create_event(name="Outra campanha", event_date=date(2025, 12, 20))

    response = client.get(reverse("christmas:event_list"), {"q": "Especial"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "christmas/event_list.html" in [
        template.name for template in response.templates if template.name
    ]
    assert matching.name in content
    assert "Outra campanha" not in content
    assert reverse("christmas:event_create") in content
    assert reverse("christmas:child_list") in content

    ChristmasEvent.objects.bulk_create(
        [
            ChristmasEvent(
                name=f"Evento {number:02d}",
                event_date=date(2024, 12, number),
                event_time="14:30",
            )
            for number in range(1, 21)
        ]
    )
    paginated_response = client.get(reverse("christmas:event_list"), {"page": 2})
    assert paginated_response.context["page_obj"].paginator.count == 22


@pytest.mark.django_db
def test_event_create_renders_form_and_saves_event(client, django_user_model):
    """Staff users should be able to create a valid event."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)

    get_response = client.get(reverse("christmas:event_create"))
    assert get_response.status_code == 200
    assert "christmas/event_form.html" in [
        template.name for template in get_response.templates if template.name
    ]
    assert 'placeholder="dd/mm/aaaa"' in get_response.content.decode()
    assert 'x-data="dateMask"' in get_response.content.decode()
    assert '@input="format($event)"' in get_response.content.decode()
    assert 'type="time"' in get_response.content.decode()

    post_response = client.post(
        reverse("christmas:event_create"),
        {
            "name": "Natal Feliz 2026",
            "event_date": "20/12/2026",
            "event_time": "14:30",
            "label_note": "Entregar o presente sem embalagem.",
        },
        follow=True,
    )

    event = ChristmasEvent.objects.get()
    assert post_response.redirect_chain == [(reverse("christmas:event_list"), 302)]
    assert event.event_date == date(2026, 12, 20)
    assert event.event_time.strftime("%H:%M") == "14:30"
    assert event.label_note == "Entregar o presente sem embalagem."


@pytest.mark.django_db
def test_event_create_rejects_invalid_submission(client, django_user_model):
    """Invalid event creation should not persist a record."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)

    response = client.post(reverse("christmas:event_create"), {})

    assert response.status_code == 200
    assert "Informe o nome do evento." in response.content.decode()
    assert not ChristmasEvent.objects.exists()


@pytest.mark.django_db
def test_event_detail_and_update(client, django_user_model):
    """Staff users should see an event and persist valid changes."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    event = _create_event(label_note="Entregar o presente sem embalagem.")

    detail_response = client.get(reverse("christmas:event_detail", args=[event.pk]))
    detail_content = detail_response.content.decode()
    assert detail_response.status_code == 200
    assert "christmas/event_detail.html" in [
        template.name for template in detail_response.templates if template.name
    ]
    assert "20/12/2026" in detail_content
    assert "14:30" in detail_content
    assert "Entregar o presente sem embalagem." in detail_content
    assert reverse("christmas:sponsorship_list", args=[event.pk]) in detail_content
    assert "Gerar etiquetas" in detail_content
    assert 'aria-disabled="true"' in detail_content

    update_url = reverse("christmas:event_update", args=[event.pk])
    update_page = client.get(update_url)
    assert 'value="20/12/2026"' in update_page.content.decode()
    assert 'value="14:30"' in update_page.content.decode()

    update_response = client.post(
        update_url,
        {
            "name": "Natal Atualizado",
            "event_date": "21/12/2026",
            "event_time": "15:00",
            "label_note": "Identificar o presente com o nome da criança.",
        },
        follow=True,
    )

    event.refresh_from_db()
    assert update_response.redirect_chain == [
        (reverse("christmas:event_detail", args=[event.pk]), 302)
    ]
    assert event.name == "Natal Atualizado"
    assert event.label_note == "Identificar o presente com o nome da criança."


@pytest.mark.django_db
def test_event_detail_links_to_labels_pdf_when_sponsorships_exist(
    client,
    django_user_model,
):
    """Event detail should open its labels PDF in a new browser tab."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    sponsorship = _create_sponsorship()

    response = client.get(
        reverse("christmas:event_detail", args=[sponsorship.event_id])
    )
    content = response.content.decode()
    labels_url = reverse(
        "christmas:event_labels_pdf",
        args=[sponsorship.event_id],
    )

    assert response.status_code == 200
    assert f'href="{labels_url}" target="_blank" rel="noopener noreferrer"' in content


@pytest.mark.django_db
def test_event_labels_pdf_requires_staff_access(client, django_user_model):
    """Only staff users should access an event's generated labels PDF."""
    sponsorship = _create_sponsorship()
    url = reverse("christmas:event_labels_pdf", args=[sponsorship.event_id])

    anonymous_response = client.get(url)
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(reverse("account_login"))

    user = _create_user(django_user_model)
    client.force_login(user)
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_event_labels_pdf_returns_inline_pdf_for_event_sponsorships(
    client,
    django_user_model,
    monkeypatch,
):
    """Staff users should receive an inline PDF containing only event records."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    event = _create_event()
    first = ChristmasSponsorship.objects.create(
        event=event,
        sponsor=_create_member(name="João Santos"),
        child=_create_child(name="Ana Silva"),
    )
    second = ChristmasSponsorship.objects.create(
        event=event,
        sponsor=_create_member(name="Paulo Lima"),
        child=_create_child(name="Beatriz Souza"),
    )
    _create_sponsorship()
    captured = {}

    def fake_generate_pdf(received_event, sponsorships):
        """Capture PDF service arguments and return deterministic content."""
        captured["event"] = received_event
        captured["sponsorships"] = sponsorships
        return b"%PDF-labels"

    monkeypatch.setattr(
        "apps.christmas.views.generate_sponsorship_labels_pdf",
        fake_generate_pdf,
    )

    response = client.get(reverse("christmas:event_labels_pdf", args=[event.pk]))

    assert response.status_code == 200
    assert response.content == b"%PDF-labels"
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.headers["Content-Disposition"] == (
        f'inline; filename="natal-feliz-evento-{event.pk}-etiquetas.pdf"'
    )
    assert captured["event"] == event
    assert [item.pk for item in captured["sponsorships"]] == [first.pk, second.pk]


@pytest.mark.django_db
def test_event_labels_pdf_returns_404_for_event_without_sponsorships(
    client,
    django_user_model,
):
    """Direct PDF access should fail when an event has no labels."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    event = _create_event()

    response = client.get(reverse("christmas:event_labels_pdf", args=[event.pk]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_event_update_rejects_invalid_submission(client, django_user_model):
    """Invalid event update should preserve the existing event."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    event = _create_event()

    response = client.post(
        reverse("christmas:event_update", args=[event.pk]),
        {"name": "", "event_date": "", "event_time": ""},
    )

    event.refresh_from_db()
    assert response.status_code == 200
    assert event.name == "Natal Feliz 2026"


@pytest.mark.django_db
def test_event_remove_cascades_sponsorship_but_preserves_related_records(
    client,
    django_user_model,
):
    """Confirmed event removal should delete its sponsorships only."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    sponsorship = _create_sponsorship()
    event = sponsorship.event
    sponsor_pk = sponsorship.sponsor_id
    child_pk = sponsorship.child_id

    get_response = client.get(reverse("christmas:event_remove", args=[event.pk]))
    assert get_response.status_code == 200
    assert "todos os seus apadrinhamentos" in get_response.content.decode()

    post_response = client.post(
        reverse("christmas:event_remove", args=[event.pk]),
        follow=True,
    )

    assert post_response.redirect_chain == [(reverse("christmas:event_list"), 302)]
    assert not ChristmasEvent.objects.filter(pk=event.pk).exists()
    assert not ChristmasSponsorship.objects.exists()
    assert Member.objects.filter(pk=sponsor_pk).exists()
    assert Child.objects.filter(pk=child_pk).exists()


@pytest.mark.django_db
def test_sponsorship_list_is_scoped_to_event_and_searches_related_names(
    client,
    django_user_model,
):
    """Sponsorship list should show only records from its selected event."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    matching = _create_sponsorship()
    other = _create_sponsorship()

    response = client.get(
        reverse("christmas:sponsorship_list", args=[matching.event_id]),
        {"q": "João"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "christmas/sponsorship_list.html" in [
        template.name for template in response.templates if template.name
    ]
    assert matching.child.name in content
    assert reverse(
        "christmas:sponsorship_create",
        args=[matching.event_id],
    ) in content
    assert reverse(
        "christmas:sponsorship_detail",
        args=[matching.event_id, matching.pk],
    ) in content
    assert other.pk != matching.pk


@pytest.mark.django_db
def test_sponsorship_create_saves_relationship_in_url_event(
    client,
    django_user_model,
):
    """Sponsorship creation should assign the event from the URL."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    event = _create_event()
    sponsor = _create_member()
    child = _create_child()
    url = reverse("christmas:sponsorship_create", args=[event.pk])

    get_response = client.get(url)
    assert get_response.status_code == 200
    assert "christmas/sponsorship_form.html" in [
        template.name for template in get_response.templates if template.name
    ]

    post_response = client.post(
        url,
        {"sponsor": sponsor.pk, "child": child.pk},
        follow=True,
    )

    sponsorship = ChristmasSponsorship.objects.get()
    assert post_response.redirect_chain == [
        (reverse("christmas:sponsorship_list", args=[event.pk]), 302)
    ]
    assert sponsorship.event == event


@pytest.mark.django_db
def test_sponsorship_create_accepts_external_natal_feliz_sponsor(
    client,
    django_user_model,
):
    """A special Natal Feliz registration should be accepted as sponsor."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    event = _create_event()
    sponsor = _create_external_sponsor()
    child = _create_child()

    response = client.post(
        reverse("christmas:sponsorship_create", args=[event.pk]),
        {"sponsor": sponsor.pk, "child": child.pk},
    )

    assert response.status_code == 302
    assert ChristmasSponsorship.objects.filter(
        event=event,
        sponsor=sponsor,
        child=child,
    ).exists()


@pytest.mark.django_db
def test_sponsor_list_shows_only_external_records_and_searches_contact(
    client,
    django_user_model,
):
    """Sponsor area should list special registrations without church members."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    matching = _create_external_sponsor(
        name="Joana Externa",
        email="joana@example.com",
    )
    _create_external_sponsor(name="Outra Pessoa")
    church_member = _create_member(name="Joana da Igreja")

    response = client.get(reverse("christmas:sponsor_list"), {"q": "joana@"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "christmas/sponsor_list.html" in [
        template.name for template in response.templates if template.name
    ]
    assert matching.name in content
    assert "Outra Pessoa" not in content
    assert church_member.name not in content
    assert reverse("christmas:sponsor_create") in content


@pytest.mark.django_db
def test_sponsor_create_forces_special_registration_and_honors_local_next(
    client,
    django_user_model,
):
    """Sponsor creation should persist special flags and return to a local URL."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    event = _create_event()
    return_url = reverse("christmas:sponsorship_create", args=[event.pk])
    create_url = reverse("christmas:sponsor_create")

    get_response = client.get(create_url, {"next": return_url})
    get_content = get_response.content.decode()
    assert get_response.status_code == 200
    assert "christmas/sponsor_form.html" in [
        template.name for template in get_response.templates if template.name
    ]
    assert 'name="name"' in get_content
    assert 'name="phone"' in get_content
    assert 'name="registration_type"' not in get_content

    response = client.post(
        create_url,
        {
            "name": "Joana Externa",
            "cpf": "123.456.789-01",
            "phone": "(11) 99999-9999",
            "email": "joana@example.com",
            "is_active": "on",
            "next": return_url,
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == return_url
    sponsor = Member.objects.get(name="Joana Externa")
    assert sponsor.registration_type == Member.RegistrationType.CHRISTMAS
    assert sponsor.is_church_member is False
    assert sponsor.include_in_birthday_list is False


@pytest.mark.django_db
def test_sponsor_create_rejects_invalid_contact(client, django_user_model):
    """Invalid contact data should re-render without creating a sponsor."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)

    response = client.post(
        reverse("christmas:sponsor_create"),
        {"name": "", "cpf": "123", "phone": "abc", "is_active": "on"},
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Informe um CPF com 11 dígitos." in content
    assert "Informe um telefone com 8 a 15 dígitos." in content
    assert not Member.objects.christmas_registrations().exists()


@pytest.mark.django_db
def test_sponsor_update_only_accepts_special_registrations(
    client,
    django_user_model,
):
    """Sponsor update should edit external records and reject church members."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    sponsor = _create_external_sponsor(phone="11999999999")
    church_member = _create_member(name="Membro da Igreja")
    update_url = reverse("christmas:sponsor_update", args=[sponsor.pk])

    get_response = client.get(update_url)
    assert get_response.status_code == 200
    assert "christmas/sponsor_form.html" in [
        template.name for template in get_response.templates if template.name
    ]
    assert sponsor.name in get_response.content.decode()

    response = client.post(
        update_url,
        {
            "name": "Padrinho Atualizado",
            "cpf": "",
            "phone": "1133334444",
            "email": "",
            "is_active": "on",
            "inactive_reason": "",
        },
    )

    assert response.status_code == 302
    sponsor.refresh_from_db()
    assert sponsor.name == "Padrinho Atualizado"
    assert sponsor.phone == "1133334444"
    assert client.get(
        reverse("christmas:sponsor_update", args=[church_member.pk])
    ).status_code == 404


@pytest.mark.django_db
def test_sponsor_update_rejects_inactive_record_without_reason(
    client,
    django_user_model,
):
    """Invalid sponsor updates should preserve the existing contact data."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    sponsor = _create_external_sponsor(phone="11999999999")

    response = client.post(
        reverse("christmas:sponsor_update", args=[sponsor.pk]),
        {
            "name": "Nome que não será salvo",
            "cpf": "",
            "phone": "11999999999",
            "email": "",
            "is_active": "",
            "inactive_reason": "",
        },
    )

    assert response.status_code == 200
    assert "Informe o motivo para inativar o cadastro." in response.content.decode()
    sponsor.refresh_from_db()
    assert sponsor.name == "Padrinho Externo"


@pytest.mark.django_db
def test_sponsor_remove_soft_deletes_record_and_preserves_sponsorship(
    client,
    django_user_model,
):
    """Removing an external sponsor should preserve historical sponsorships."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    sponsor = _create_external_sponsor()
    sponsorship = _create_sponsorship(sponsor=sponsor)
    remove_url = reverse("christmas:sponsor_remove", args=[sponsor.pk])

    get_response = client.get(remove_url)
    assert get_response.status_code == 200
    assert "christmas/sponsor_confirm_remove.html" in [
        template.name for template in get_response.templates if template.name
    ]

    response = client.post(remove_url)

    assert response.status_code == 302
    assert not Member.objects.filter(pk=sponsor.pk).exists()
    assert Member.all_objects.filter(pk=sponsor.pk).exists()
    assert ChristmasSponsorship.objects.filter(pk=sponsorship.pk).exists()


@pytest.mark.django_db
def test_sponsorship_form_renders_searchable_member_and_child_choices(
    client,
    django_user_model,
):
    """The sponsorship form should enhance its existing choices with Alpine.js."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    event = _create_event()
    _create_member(name="João Santos")
    _create_child(name="Ágata Silva")

    response = client.get(reverse("christmas:sponsorship_create", args=[event.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert content.count('x-data="searchableSelect()"') == 2
    assert content.count('role="combobox"') == 2
    assert 'name="sponsor"' in content
    assert 'name="child"' in content
    assert "João Santos" in content
    assert "Ágata Silva" in content
    assert "Nenhum resultado encontrado." in content


@pytest.mark.django_db
def test_sponsorship_create_rejects_duplicate_child_in_event(
    client,
    django_user_model,
):
    """Creation should reject a second sponsor for a child in the same event."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    existing = _create_sponsorship()
    second_sponsor = _create_member(name="Paulo Lima")

    response = client.post(
        reverse("christmas:sponsorship_create", args=[existing.event_id]),
        {"sponsor": second_sponsor.pk, "child": existing.child_id},
    )

    assert response.status_code == 200
    assert "Esta criança já possui um padrinho neste evento." in (
        response.content.decode()
    )
    assert ChristmasSponsorship.objects.count() == 1


@pytest.mark.django_db
def test_sponsorship_detail_and_update(client, django_user_model):
    """Staff users should see a sponsorship and persist valid changes."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    sponsorship = _create_sponsorship()
    new_sponsor = _create_member(name="Paulo Lima")

    detail_url = reverse(
        "christmas:sponsorship_detail",
        args=[sponsorship.event_id, sponsorship.pk],
    )
    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert sponsorship.event.name in detail_response.content.decode()
    assert "Tamanho da roupa" in detail_response.content.decode()

    update_response = client.post(
        reverse(
            "christmas:sponsorship_update",
            args=[sponsorship.event_id, sponsorship.pk],
        ),
        {"sponsor": new_sponsor.pk, "child": sponsorship.child_id},
        follow=True,
    )

    sponsorship.refresh_from_db()
    assert update_response.redirect_chain == [(detail_url, 302)]
    assert sponsorship.sponsor == new_sponsor


@pytest.mark.django_db
def test_sponsorship_update_rejects_duplicate_child_in_event(
    client,
    django_user_model,
):
    """Invalid updates should preserve the existing sponsorship."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    event = _create_event()
    first = _create_sponsorship(event=event)
    second = _create_sponsorship(
        event=event,
        sponsor=_create_member(name="Paulo Lima"),
        child=_create_child(name="Beatriz Souza", mother_name="Clara Souza"),
    )

    response = client.post(
        reverse(
            "christmas:sponsorship_update",
            args=[event.pk, second.pk],
        ),
        {"sponsor": second.sponsor_id, "child": first.child_id},
    )

    second.refresh_from_db()
    assert response.status_code == 200
    assert "Esta criança já possui um padrinho neste evento." in (
        response.content.decode()
    )
    assert second.child.name == "Beatriz Souza"


@pytest.mark.django_db
def test_sponsorship_remove_permanently_deletes_relationship(
    client,
    django_user_model,
):
    """Confirmed removal should delete only the sponsorship relationship."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    sponsorship = _create_sponsorship()
    event_pk = sponsorship.event_id
    sponsor_pk = sponsorship.sponsor_id
    child_pk = sponsorship.child_id
    url = reverse(
        "christmas:sponsorship_remove",
        args=[event_pk, sponsorship.pk],
    )

    assert client.get(url).status_code == 200
    post_response = client.post(url, follow=True)

    assert post_response.redirect_chain == [
        (reverse("christmas:sponsorship_list", args=[event_pk]), 302)
    ]
    assert not ChristmasSponsorship.objects.exists()
    assert Member.objects.filter(pk=sponsor_pk).exists()
    assert Child.objects.filter(pk=child_pk).exists()


@pytest.mark.django_db
def test_sponsorship_detail_returns_404_for_another_event(
    client,
    django_user_model,
):
    """A sponsorship should not be accessible through another event URL."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    sponsorship = _create_sponsorship()
    other_event = _create_event(name="Outro evento")

    response = client.get(
        reverse(
            "christmas:sponsorship_detail",
            args=[other_event.pk, sponsorship.pk],
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_child_list_renders_and_filters_by_child_or_mother_name(
    client,
    django_user_model,
):
    """Child list should render and search child and mother names."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    matching_child = Child.objects.create(
        name="Ana Silva",
        mother_name="Maria Oliveira",
        birth_date=date(2018, 5, 12),
        clothing_size=8,
    )
    other_child = Child.objects.create(
        name="Beatriz Souza",
        mother_name="Clara Souza",
        birth_date=date(2019, 6, 10),
        clothing_size=10,
    )

    response = client.get(reverse("christmas:child_list"), {"q": "Oliveira"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "christmas/child_list.html" in [
        template.name for template in response.templates if template.name
    ]
    assert matching_child.name in content
    assert other_child.name not in content
    assert "12/05/2018" in content
    assert "Tamanho da roupa" in content
    assert reverse("christmas:child_detail", args=[matching_child.pk]) in content
    assert reverse("christmas:child_update", args=[matching_child.pk]) in content
    assert reverse("christmas:child_remove", args=[matching_child.pk]) in content


@pytest.mark.django_db
def test_child_list_paginates_and_preserves_search_query(client, django_user_model):
    """Child list should paginate results and preserve its search query."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    Child.objects.bulk_create(
        [
            Child(
                name=f"Criança {number:02d}",
                mother_name=f"Mãe {number:02d}",
                birth_date=date(2018, 1, 1),
            )
            for number in range(1, 22)
        ]
    )

    response = client.get(
        reverse("christmas:child_list"),
        {"q": "Criança", "page": 2},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["page_obj"].paginator.count == 21
    assert "Criança 21" in content
    assert "?q=Crian%C3%A7a&amp;page=1" in content


@pytest.mark.django_db
def test_child_create_page_renders_form(client, django_user_model):
    """Staff users should see the child creation form."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)

    response = client.get(reverse("christmas:child_create"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "christmas/child_form.html" in [
        template.name for template in response.templates if template.name
    ]
    assert 'name="birth_date"' in content
    assert 'name="clothing_size"' in content
    assert 'placeholder="dd/mm/aaaa"' in content
    assert 'x-data="dateMask"' in content
    assert '@input="format($event)"' in content


@pytest.mark.django_db
def test_child_create_saves_and_redirects_to_list(client, django_user_model):
    """Valid child submission should create a record and return to the list."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)

    response = client.post(
        reverse("christmas:child_create"),
        {
            "name": "Ana Silva",
            "mother_name": "Maria Silva",
            "birth_date": "12/05/2018",
            "clothing_size": "8",
        },
        follow=True,
    )

    child = Child.objects.get()
    assert response.status_code == 200
    assert response.redirect_chain == [(reverse("christmas:child_list"), 302)]
    assert "Criança Ana Silva cadastrada com sucesso." in response.content.decode()
    assert child.name == "Ana Silva"
    assert child.birth_date == date(2018, 5, 12)
    assert child.clothing_size == 8


@pytest.mark.django_db
def test_child_create_rejects_invalid_submission(client, django_user_model):
    """Invalid child submission should re-render without creating a record."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)

    response = client.post(
        reverse("christmas:child_create"),
        {"name": "", "mother_name": "", "birth_date": "", "clothing_size": ""},
    )

    assert response.status_code == 200
    assert "Informe o nome da criança." in response.content.decode()
    assert not Child.objects.exists()


@pytest.mark.django_db
def test_child_detail_renders_registration(client, django_user_model):
    """Child detail should display all campaign registration data."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    child = _create_child()

    response = client.get(reverse("christmas:child_detail", args=[child.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "christmas/child_detail.html" in [
        template.name for template in response.templates if template.name
    ]
    assert child.name in content
    assert child.mother_name in content
    assert "12/05/2018" in content
    assert "Tamanho da roupa" in content
    assert ">8<" in content
    assert reverse("christmas:child_update", args=[child.pk]) in content
    assert reverse("christmas:child_remove", args=[child.pk]) in content


@pytest.mark.django_db
def test_child_update_renders_existing_data_and_saves_changes(
    client,
    django_user_model,
):
    """Child update should render and persist valid edited data."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    child = _create_child()
    update_url = reverse("christmas:child_update", args=[child.pk])

    get_response = client.get(update_url)
    get_content = get_response.content.decode()
    assert get_response.status_code == 200
    assert 'value="12/05/2018"' in get_content
    assert 'name="clothing_size"' in get_content
    assert 'value="8"' in get_content
    assert f"Editar {child.name}" in get_content

    post_response = client.post(
        update_url,
        {
            "name": "Ana Silva Atualizada",
            "mother_name": "Maria Oliveira",
            "birth_date": "20/06/2018",
            "clothing_size": "10",
        },
        follow=True,
    )

    child.refresh_from_db()
    assert post_response.status_code == 200
    assert post_response.redirect_chain == [
        (reverse("christmas:child_detail", args=[child.pk]), 302)
    ]
    assert "Cadastro de Ana Silva Atualizada atualizado com sucesso." in (
        post_response.content.decode()
    )
    assert child.name == "Ana Silva Atualizada"
    assert child.mother_name == "Maria Oliveira"
    assert child.birth_date == date(2018, 6, 20)
    assert child.clothing_size == 10


@pytest.mark.django_db
def test_child_update_rejects_invalid_submission(client, django_user_model):
    """Invalid child update should preserve the existing record."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    child = _create_child()

    response = client.post(
        reverse("christmas:child_update", args=[child.pk]),
        {"name": "", "mother_name": "", "birth_date": "", "clothing_size": ""},
    )

    child.refresh_from_db()
    assert response.status_code == 200
    assert "Informe o nome da criança." in response.content.decode()
    assert child.name == "Ana Silva"


@pytest.mark.django_db
def test_child_remove_page_renders_confirmation(client, django_user_model):
    """Child removal should display a confirmation page before deletion."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    child = _create_child()

    response = client.get(reverse("christmas:child_remove", args=[child.pk]))

    assert response.status_code == 200
    assert "christmas/child_confirm_remove.html" in [
        template.name for template in response.templates if template.name
    ]
    assert "preserva o cadastro no banco" in response.content.decode()


@pytest.mark.django_db
def test_child_remove_soft_deletes_and_hides_registration(
    client,
    django_user_model,
):
    """Confirmed removal should preserve the child outside ordinary queries."""
    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    child = _create_child()
    child_pk = child.pk

    response = client.post(
        reverse("christmas:child_remove", args=[child.pk]),
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain == [(reverse("christmas:child_list"), 302)]
    assert "Criança Ana Silva removida da lista com sucesso." in (
        response.content.decode()
    )
    assert not Child.objects.filter(pk=child_pk).exists()
    assert Child.all_objects.filter(pk=child_pk, deleted_at__isnull=False).exists()
    assert (
        client.get(reverse("christmas:child_detail", args=[child_pk])).status_code
        == 404
    )


@pytest.mark.django_db
def test_header_shows_christmas_link_only_to_staff(client, django_user_model):
    """Header should expose Natal Feliz navigation only to staff users."""
    user = _create_user(django_user_model)
    client.force_login(user)
    response = client.get(reverse("members:list"))
    assert reverse("christmas:event_list") not in response.content.decode()

    staff_user = _create_user(django_user_model, is_staff=True)
    client.force_login(staff_user)
    response = client.get(reverse("members:list"))
    content = response.content.decode()
    assert f'href="{reverse("birthdays:settings")}"' in content
    assert f'href="{reverse("christmas:event_list")}"' in content
    assert content.index("Aniversariantes") < content.index("Natal Feliz")
