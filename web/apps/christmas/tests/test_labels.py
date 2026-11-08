"""Tests for Natal Feliz sponsorship label generation."""

import re
import subprocess
from datetime import date, time
from types import SimpleNamespace
from unittest.mock import MagicMock

from playwright import sync_api

from apps.christmas.services import labels


def _sponsorship(number):
    """Return a sponsorship-like object for label service tests."""
    return SimpleNamespace(
        pk=number,
        sponsor=SimpleNamespace(name=f"Padrinho {number}"),
        child=SimpleNamespace(
            name=f"Criança {number}",
            mother_name=f"Mãe {number}",
            birth_date=date(2018, 5, 12),
            clothing_size=8,
        ),
    )


def test_label_pages_group_sponsorships_six_at_a_time():
    """Thirteen sponsorships should produce pages containing 6, 6, and 1 labels."""
    event = SimpleNamespace(event_date=date(2026, 12, 20))
    pages = labels.build_sponsorship_label_pages(
        event,
        [_sponsorship(number) for number in range(1, 14)]
    )

    assert [len(page) for page in pages] == [6, 6, 1]
    assert pages[0][0] == {
        "number": 1,
        "sponsor_name": "Padrinho 1",
        "child_name": "Criança 1",
        "mother_name": "Mãe 1",
        "age": 8,
        "clothing_size": 8,
    }


def test_label_numbers_are_sequential_regardless_of_sponsorship_ids():
    """Printed numbers should start at one and ignore gaps in database IDs."""
    event = SimpleNamespace(event_date=date(2026, 12, 20))
    sponsorships = [_sponsorship(number) for number in (3, 8, 15, 21, 34, 55, 89)]

    pages = labels.build_sponsorship_label_pages(event, sponsorships)

    assert [[label["number"] for label in page] for page in pages] == [
        [1, 2, 3, 4, 5, 6],
        [7],
    ]


def test_checklist_entries_match_the_labels_order_and_information():
    """Checklist entries should reuse the exact ordered data printed on labels."""
    event = SimpleNamespace(event_date=date(2026, 12, 20))
    sponsorships = [_sponsorship(number) for number in (8, 3, 15)]

    entries = labels.build_sponsorship_entries(event, sponsorships)
    label_entries = [
        entry
        for page in labels.build_sponsorship_label_pages(event, sponsorships)
        for entry in page
    ]

    assert entries == label_entries
    assert [entry["number"] for entry in entries] == [1, 2, 3]


def test_label_formats_each_word_of_sponsor_name():
    """Sponsor names should be printed with title-style capitalization."""
    event = SimpleNamespace(event_date=date(2026, 12, 20))
    sponsorship = _sponsorship(1)
    sponsorship.sponsor.name = "jOÃO cARLOS DA sILVA"

    pages = labels.build_sponsorship_label_pages(event, [sponsorship])

    assert pages[0][0]["sponsor_name"] == "João Carlos Da Silva"


def test_age_is_calculated_on_event_date():
    """A child's age should reflect whether their birthday passed by the event."""
    birth_date = date(2018, 12, 21)

    assert labels.calculate_age_on_date(birth_date, date(2026, 12, 20)) == 7
    assert labels.calculate_age_on_date(birth_date, date(2026, 12, 21)) == 8


def test_labels_html_contains_complete_label_information():
    """Rendered HTML should contain all printable sponsorship information."""
    event = SimpleNamespace(
        name="Natal Feliz 2026",
        event_date=date(2026, 12, 20),
        event_time=time(14, 30),
        label_note="Entregar o presente sem embalagem.",
    )
    html = labels.render_sponsorship_labels_html(
        event,
        [_sponsorship(number) for number in range(1, 14)],
    )

    assert html.count('<section class="label-sheet">') == 3
    assert html.count('<article class="sponsorship-label">') == 13
    assert "border: 1px solid #000" in html
    assert '<p class="sponsorship-number">Nº 1</p>' in html
    assert html.count('<p class="event-name">Natal Feliz 2026</p>') == 13
    assert '<h2 class="child-name">CRIANÇA 1</h2>' in html
    assert "font-size: 28pt" in html
    assert "margin: 3mm 0 2mm" in html
    assert "font-size: 14.5pt" in html
    assert "text-transform: uppercase" in html
    assert "width: 21mm" in html
    assert "height: 21mm" in html
    assert "min-height: 21mm" in html
    assert "padding: 2mm 0" in html
    assert "break-inside: avoid-page" in html
    assert "page-break-inside: avoid" in html
    assert "\n        break-inside: avoid;\n" not in html
    assert "<strong>Mãe:</strong> Mãe 1" in html
    assert "<strong>Padrinho:</strong> Padrinho 1" in html
    assert "<strong>Idade:</strong> 8 anos" in html
    assert "<strong>Tamanho da roupa:</strong> 8" in html
    assert html.count("<strong>Observação:</strong>") == 13
    assert "Entregar o presente sem embalagem." in html
    assert "Festa dia: 20/12/2026" in html
    assert "Horário: 14:30" in html
    assert "color: #c62828" in html
    assert 'src="data:image/webp;base64,' in html
    assert 'alt="Logo da Comuna Bristol"' in html


def test_labels_html_omits_empty_event_note():
    """Rendered labels should omit the observation line when no note was provided."""
    event = SimpleNamespace(
        name="Natal Feliz 2026",
        event_date=date(2026, 12, 20),
        event_time=time(14, 30),
        label_note="",
    )

    html = labels.render_sponsorship_labels_html(event, [_sponsorship(1)])

    assert "<strong>Observação:</strong>" not in html


def test_checklist_html_contains_compact_conference_blocks():
    """Rendered checklist should show event data once and one marked block per item."""
    event = SimpleNamespace(
        name="Natal Feliz 2026",
        event_date=date(2026, 12, 20),
        event_time=time(14, 30),
        label_note="Entregar o presente sem embalagem.",
    )

    html = labels.render_sponsorship_checklist_html(
        event,
        [_sponsorship(number) for number in range(1, 4)],
    )

    assert html.count('<article class="checklist-entry">') == 3
    assert html.count("Lista de conferência") == 2
    assert html.count("Natal Feliz 2026") == 2
    assert html.count("Entregar o presente sem embalagem.") == 1
    assert html.count("Conferido</span>") == 3
    assert '<p class="entry-number">Nº 1</p>' in html
    assert '<h2 class="child-name">CRIANÇA 1</h2>' in html
    assert "<strong>Mãe:</strong> Mãe 1" in html
    assert "<strong>Padrinho:</strong> Padrinho 1" in html
    assert "<strong>Idade:</strong> 8 anos" in html
    assert "<strong>Tamanho da roupa:</strong> 8" in html
    assert "<strong>Data:</strong> 20/12/2026" in html
    assert "<strong>Horário:</strong> 14:30" in html
    assert "break-inside: avoid-page" in html
    assert "page-break-inside: avoid" in html
    assert 'src="data:image/webp;base64,' in html


def test_checklist_html_omits_empty_event_note():
    """Checklist header should omit the observation when none was provided."""
    event = SimpleNamespace(
        name="Natal Feliz 2026",
        event_date=date(2026, 12, 20),
        event_time=time(14, 30),
        label_note="",
    )

    html = labels.render_sponsorship_checklist_html(event, [_sponsorship(1)])

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
        SimpleNamespace(
            name="Natal Feliz 2026",
            event_date=date(2026, 12, 20),
            event_time=time(14, 30),
            label_note="",
        ),
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


def test_pdf_keeps_wrapped_labels_on_their_expected_pages(tmp_path):
    """Wrapped label content should not move or overlap the following page."""
    event = SimpleNamespace(
        name="Natal Feliz 2026",
        event_date=date(2026, 12, 12),
        event_time=time(10, 30),
        label_note="1 Roupa, 1 Brinquedo, 1 Cx de Bombom",
    )
    sponsorships = [_sponsorship(number) for number in range(1, 34)]
    wrapped_content = {
        12: (
            "Agatha Sophia Campos Machado Silva",
            "Victória Beatriz Maria da Silva Oliveira",
        ),
        18: (
            "Isaac Rodrigues da Silva",
            "Francisca Ecielda Siqueira Moreira",
        ),
        30: (
            "Maria Júlia Pedro Costa",
            "Walquíria Batista dos Santos Trindade",
        ),
    }
    for number, (child_name, sponsor_name) in wrapped_content.items():
        sponsorships[number - 1].child.name = child_name
        sponsorships[number - 1].sponsor.name = sponsor_name

    pdf_path = tmp_path / "labels.pdf"
    pdf_path.write_bytes(labels.generate_sponsorship_labels_pdf(event, sponsorships))
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    page_numbers = [
        [int(number) for number in re.findall(r"Nº\s+(\d+)", page)]
        for page in result.stdout.split("\f")
        if page.strip()
    ]

    assert page_numbers == [
        [1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12],
        [13, 14, 15, 16, 17, 18],
        [19, 20, 21, 22, 23, 24],
        [25, 26, 27, 28, 29, 30],
        [31, 32, 33],
    ]
