"""Tests for birthday report image helpers."""

from datetime import date
from types import SimpleNamespace

from apps.birthdays.services import images


def test_birthday_image_entries_use_member_presigned_photo_url():
    """Birthday reports should give Playwright the same member URL as the list."""
    class Photo:
        """Photo-like object that must not be opened during report generation."""

        url = "https://s3.example.com/mdc-media/media/members/maria.jpg?signature=example"

        def __bool__(self):
            """Indicate that the member has a photo."""
            return True

        def open(self, mode):
            """Fail if report generation reads from the storage backend."""
            raise AssertionError("Report generation should use the presigned URL")

    member = SimpleNamespace(
        name="Maria Silva",
        birthday_occurrence=date(2026, 7, 22),
        photo=Photo(),
    )

    entry = images.build_birthday_image_entries([member])[0]
    html = images.render_birthday_report_html(
        [member],
        date(2026, 7, 20),
        date(2026, 7, 26),
    )

    assert entry["photo_url"] == member.photo.url
    assert f'src="{member.photo.url}"' in html


def test_birthday_image_entries_use_default_photo_without_member_photo():
    """Birthday reports should use the default image when no photo exists."""
    member = SimpleNamespace(
        name="Maria Silva",
        birthday_occurrence=date(2026, 7, 22),
        photo=None,
    )

    entry = images.build_birthday_image_entries([member])[0]

    assert entry["photo_url"] == images.DEFAULT_PHOTO_DATA_URL
