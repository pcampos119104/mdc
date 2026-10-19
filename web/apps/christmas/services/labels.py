"""PDF label generation for Natal Feliz sponsorships."""

import base64
from pathlib import Path

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string


LABELS_PER_PAGE = 6
CHURCH_LOGO_PATH = "img/comuna-bristol-logo.webp"


def calculate_age_on_date(birth_date, reference_date):
    """Return the age reached by a child on the reference date."""
    birthday_has_passed = (reference_date.month, reference_date.day) >= (
        birth_date.month,
        birth_date.day,
    )
    return reference_date.year - birth_date.year - (not birthday_has_passed)


def build_sponsorship_label_pages(event, sponsorships):
    """Return sponsorship label entries grouped into pages of six."""
    entries = [
        {
            "number": number,
            "sponsor_name": sponsorship.sponsor.name,
            "child_name": sponsorship.child.name,
            "mother_name": sponsorship.child.mother_name,
            "age": calculate_age_on_date(
                sponsorship.child.birth_date,
                event.event_date,
            ),
            "clothing_size": sponsorship.child.clothing_size,
        }
        for number, sponsorship in enumerate(sponsorships, start=1)
    ]
    return [
        entries[index : index + LABELS_PER_PAGE]
        for index in range(0, len(entries), LABELS_PER_PAGE)
    ]


def church_logo_data_uri():
    """Return the church logo as a data URI suitable for standalone HTML."""
    logo_path = finders.find(CHURCH_LOGO_PATH)
    if not logo_path:
        raise FileNotFoundError(f"Static church logo not found: {CHURCH_LOGO_PATH}")

    encoded_logo = base64.b64encode(Path(logo_path).read_bytes()).decode("ascii")
    return f"data:image/webp;base64,{encoded_logo}"


def render_sponsorship_labels_html(event, sponsorships):
    """Render printable HTML labels for an event's sponsorships."""
    return render_to_string(
        "christmas/sponsorship_labels_pdf.html",
        {
            "event": event,
            "logo_data_uri": church_logo_data_uri(),
            "pages": build_sponsorship_label_pages(event, sponsorships),
        },
    )


def generate_sponsorship_labels_pdf(event, sponsorships):
    """Generate an A4 portrait PDF containing six sponsorship labels per page."""
    from playwright.sync_api import sync_playwright

    html = render_sponsorship_labels_html(event, sponsorships)
    browser = None
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            page.evaluate("document.fonts && document.fonts.ready")
            return page.pdf(
                format="A4",
                landscape=False,
                print_background=True,
                prefer_css_page_size=True,
            )
        finally:
            if browser is not None:
                browser.close()
