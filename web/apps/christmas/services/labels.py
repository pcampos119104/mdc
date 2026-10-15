"""PDF label generation for Natal Feliz sponsorships."""

from django.template.loader import render_to_string


LABELS_PER_PAGE = 6


def build_sponsorship_label_pages(sponsorships):
    """Return sponsorship label entries grouped into pages of six."""
    entries = [
        {
            "id": sponsorship.pk,
            "sponsor_name": sponsorship.sponsor.name,
            "child_name": sponsorship.child.name,
        }
        for sponsorship in sponsorships
    ]
    return [
        entries[index : index + LABELS_PER_PAGE]
        for index in range(0, len(entries), LABELS_PER_PAGE)
    ]


def render_sponsorship_labels_html(event, sponsorships):
    """Render printable HTML labels for an event's sponsorships."""
    return render_to_string(
        "christmas/sponsorship_labels_pdf.html",
        {
            "event": event,
            "pages": build_sponsorship_label_pages(sponsorships),
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
