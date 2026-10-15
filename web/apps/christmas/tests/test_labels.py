"""Tests for Natal Feliz sponsorship label generation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from playwright import sync_api

from apps.christmas.services import labels


def _sponsorship(number):
    """Return a sponsorship-like object for label service tests."""
    return SimpleNamespace(
        pk=number,
        sponsor=SimpleNamespace(name=f"Padrinho {number}"),
        child=SimpleNamespace(name=f"Criança {number}"),
    )


def test_label_pages_group_sponsorships_six_at_a_time():
    """Thirteen sponsorships should produce pages containing 6, 6, and 1 labels."""
    pages = labels.build_sponsorship_label_pages(
        [_sponsorship(number) for number in range(1, 14)]
    )

    assert [len(page) for page in pages] == [6, 6, 1]
    assert pages[0][0] == {
        "id": 1,
        "sponsor_name": "Padrinho 1",
        "child_name": "Criança 1",
    }


def test_labels_html_contains_sheets_borders_and_identification():
    """Rendered HTML should contain one bordered card per sponsorship."""
    event = SimpleNamespace(
        name="Natal Feliz 2026",
        label_note="Entregar o presente sem embalagem.",
    )
    html = labels.render_sponsorship_labels_html(
        event,
        [_sponsorship(number) for number in range(1, 14)],
    )

    assert html.count('<section class="label-sheet">') == 3
    assert html.count('<article class="sponsorship-label">') == 13
    assert "border: 1px solid #000" in html
    assert "<strong>ID:</strong> 1" in html
    assert "<strong>Padrinho:</strong> Padrinho 1" in html
    assert "<strong>Criança:</strong> Criança 1" in html
    assert html.count("<strong>Observação:</strong>") == 13
    assert "Entregar o presente sem embalagem." in html


def test_labels_html_omits_empty_event_note():
    """Rendered labels should omit the observation line when no note was provided."""
    event = SimpleNamespace(name="Natal Feliz 2026", label_note="")

    html = labels.render_sponsorship_labels_html(event, [_sponsorship(1)])

    assert "<strong>Observação:</strong>" not in html


def test_pdf_generation_uses_a4_portrait_playwright_options(monkeypatch):
    """PDF generation should configure Chromium for printable A4 portrait output."""
    manager = MagicMock()
    playwright = manager.__enter__.return_value
    browser = playwright.chromium.launch.return_value
    page = browser.new_page.return_value
    page.pdf.return_value = b"%PDF-labels"
    monkeypatch.setattr(sync_api, "sync_playwright", lambda: manager)

    content = labels.generate_sponsorship_labels_pdf(
        SimpleNamespace(name="Natal Feliz 2026"),
        [_sponsorship(1)],
    )

    assert content == b"%PDF-labels"
    playwright.chromium.launch.assert_called_once_with(
        headless=True,
        args=["--no-sandbox"],
    )
    page.pdf.assert_called_once_with(
        format="A4",
        landscape=False,
        print_background=True,
        prefer_css_page_size=True,
    )
    browser.close.assert_called_once_with()
