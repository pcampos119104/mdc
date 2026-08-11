"""Tests for birthday report image helpers."""

import base64
from datetime import date
from io import BytesIO
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.birthdays.services import images
from apps.members.models import Member


def _image_upload(name="member.png", size=(1200, 800), image_format="PNG"):
    """Return an in-memory image upload for report image tests."""
    image_content = BytesIO()
    Image.new("RGB", size, (29, 78, 216)).save(image_content, format=image_format)
    return SimpleUploadedFile(
        name,
        image_content.getvalue(),
        content_type=f"image/{image_format.lower()}",
    )


@pytest.mark.django_db
def test_birthday_image_entries_embed_small_jpeg_photo(settings, tmp_path):
    """Birthday report entries should embed compact JPEG photo data URLs."""
    settings.MEDIA_ROOT = tmp_path
    member = Member.objects.create(
        name="Maria Silva",
        birth_date=date(1990, 7, 22),
        photo=_image_upload(),
    )
    member.birthday_occurrence = date(2026, 7, 22)

    entry = images.build_birthday_image_entries([member])[0]

    assert entry["photo_data_url"].startswith("data:image/jpeg;base64,")
    encoded_content = entry["photo_data_url"].removeprefix("data:image/jpeg;base64,")
    with Image.open(BytesIO(base64.b64decode(encoded_content))) as report_photo:
        assert report_photo.format == "JPEG"
        assert max(report_photo.size) <= images.BIRTHDAY_PHOTO_MAX_DIMENSION


def test_birthday_image_entries_use_default_photo_for_large_sources():
    """Birthday report entries should skip source photos above the safe size."""

    class LargePhoto:
        """Photo-like object that should not be opened because it is too large."""

        def __bool__(self):
            """Return true so the helper treats this as an existing photo."""
            return True

        def open(self, mode):
            """Mirror Django file field open behavior."""

        def read(self, size):
            """Return content just above the allowed source size."""
            assert size == images.BIRTHDAY_PHOTO_MAX_SOURCE_SIZE + 1
            return b"x" * size

        def close(self):
            """Mirror Django file field close behavior for the helper."""

    member = SimpleNamespace(
        name="Maria Silva",
        birthday_occurrence=date(2026, 7, 22),
        photo=LargePhoto(),
    )

    entry = images.build_birthday_image_entries([member])[0]

    assert entry["photo_data_url"] == images.DEFAULT_PHOTO_DATA_URL


def test_birthday_image_entries_use_default_photo_when_open_fails():
    """Birthday report entries should keep rendering when a photo cannot be read."""

    class BrokenPhoto:
        """Photo-like object that raises while being opened."""

        name = "broken.jpg"
        size = 100

        def __bool__(self):
            """Return true so the helper treats this as an existing photo."""
            return True

        def open(self, mode):
            """Simulate a storage read failure."""
            raise OSError("storage unavailable")

        def close(self):
            """Mirror Django file field close behavior for the helper."""

    member = SimpleNamespace(
        name="Maria Silva",
        birthday_occurrence=date(2026, 7, 22),
        photo=BrokenPhoto(),
    )

    entry = images.build_birthday_image_entries([member])[0]

    assert entry["photo_data_url"] == images.DEFAULT_PHOTO_DATA_URL
