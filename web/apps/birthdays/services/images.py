"""HTML to JPEG rendering service for birthday reports."""

import base64
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string


DEFAULT_PHOTO_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
  <rect width="160" height="160" rx="80" fill="#dbeafe"/>
  <circle cx="80" cy="62" r="30" fill="#1d4ed8" opacity="0.85"/>
  <path d="M33 138c8-30 25-46 47-46s39 16 47 46" fill="#1d4ed8" opacity="0.85"/>
</svg>
""".strip()

DEFAULT_PHOTO_DATA_URL = "data:image/svg+xml;base64," + base64.b64encode(
    DEFAULT_PHOTO_SVG.encode("utf-8")
).decode("ascii")


def _read_tailwind_css():
    """Return compiled Tailwind CSS when available for image rendering."""
    css_path = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
    if not css_path.exists():
        return ""
    return css_path.read_text(encoding="utf-8")


def build_birthday_image_entries(members):
    """Return template entries with presigned photo URLs or a default image."""
    return [
        {
            "name": member.name,
            "birthday_occurrence": member.birthday_occurrence,
            "photo_url": member.photo.url if member.photo else DEFAULT_PHOTO_DATA_URL,
        }
        for member in members
    ]


def render_birthday_report_html(members, period_start, period_end):
    """Render the birthday report HTML that will be captured as an image."""
    return render_to_string(
        "birthdays/birthday_report_image.html",
        {
            "entries": build_birthday_image_entries(members),
            "period_start": period_start,
            "period_end": period_end,
            "tailwind_css": _read_tailwind_css(),
        },
    )


def generate_birthday_report_image(members, period_start, period_end):
    """Generate a JPEG image from the birthday report Django template."""
    from playwright.sync_api import sync_playwright

    html = render_birthday_report_html(members, period_start, period_end)
    browser = None
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(
                viewport={"width": 900, "height": 1400},
                device_scale_factor=1,
            )
            page.set_content(html, wait_until="networkidle")
            page.evaluate("document.fonts && document.fonts.ready")
            page.evaluate(
                """
                async () => {
                  await Promise.all(Array.from(document.images).map((img) => {
                    if (img.complete) return Promise.resolve();
                    return new Promise((resolve) => {
                      img.addEventListener('load', resolve, { once: true });
                      img.addEventListener('error', resolve, { once: true });
                    });
                  }));
                }
                """
            )
            container = page.locator("#birthday-report-image")
            return container.screenshot(type="jpeg", quality=90)
        finally:
            if browser is not None:
                browser.close()
