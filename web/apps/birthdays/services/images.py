"""HTML to JPEG rendering service for birthday reports."""

import base64
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from PIL import Image, ImageOps
from storages.backends.s3 import S3Storage


BIRTHDAY_PHOTO_MAX_DIMENSION = 256
BIRTHDAY_PHOTO_MAX_SOURCE_SIZE = 5 * 1024 * 1024
BIRTHDAY_PHOTO_JPEG_QUALITY = 85


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


def _file_to_data_url(field_file):
    """Return a data URL for a Django file field or a default image."""
    if not field_file:
        return DEFAULT_PHOTO_DATA_URL

    try:
        storage = getattr(field_file, "storage", None)
        if isinstance(storage, S3Storage):
            response = storage.connection.meta.client.get_object(
                Bucket=storage.bucket_name,
                Key=storage._normalize_name(field_file.name),
            )
            source_file = response["Body"]
            try:
                if response["ContentLength"] > BIRTHDAY_PHOTO_MAX_SOURCE_SIZE:
                    return DEFAULT_PHOTO_DATA_URL
                content = source_file.read()
            finally:
                source_file.close()
        else:
            if field_file.size > BIRTHDAY_PHOTO_MAX_SOURCE_SIZE:
                return DEFAULT_PHOTO_DATA_URL

            field_file.open("rb")
            content = field_file.read()
    except Exception:
        return DEFAULT_PHOTO_DATA_URL
    finally:
        try:
            field_file.close()
        except Exception:
            pass

    try:
        return _image_content_to_data_url(content)
    except Exception:
        return DEFAULT_PHOTO_DATA_URL


def _image_content_to_data_url(content):
    """Return a small JPEG data URL for image bytes."""
    with Image.open(BytesIO(content)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail(
            (BIRTHDAY_PHOTO_MAX_DIMENSION, BIRTHDAY_PHOTO_MAX_DIMENSION),
            Image.Resampling.LANCZOS,
        )
        image = _to_rgb_image(image)

        output = BytesIO()
        image.save(
            output,
            format="JPEG",
            quality=BIRTHDAY_PHOTO_JPEG_QUALITY,
            optimize=True,
        )

    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _to_rgb_image(image):
    """Return an RGB image suitable for JPEG report embedding."""
    if image.mode == "RGB":
        return image

    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        return background

    return image.convert("RGB")


def build_birthday_image_entries(members):
    """Return template entries with embedded photo data URLs."""
    return [
        {
            "name": member.name,
            "birthday_occurrence": member.birthday_occurrence,
            "photo_data_url": _file_to_data_url(member.photo),
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
