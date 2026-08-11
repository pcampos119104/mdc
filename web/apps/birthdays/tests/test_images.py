"""Tests for birthday report image helpers."""

import base64
from datetime import date
from io import BytesIO
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from storages.backends.s3 import S3Storage

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


def test_birthday_image_entries_read_s3_photos_without_head_object():
    """Birthday report entries should read S3 photos with GetObject directly."""
    class SourceFile:
        """In-memory S3 response body that records closure."""

        def __init__(self, content):
            """Store image bytes for the simulated S3 response."""
            self.content = content
            self.closed = False

        def read(self):
            """Return the simulated S3 object content."""
            return self.content

        def close(self):
            """Record that the streaming response body was closed."""
            self.closed = True

    class S3Client:
        """S3 client double that records direct object reads."""

        def __init__(self, source_file):
            """Configure the S3 response body."""
            self.source_file = source_file
            self.calls = []

        def get_object(self, **kwargs):
            """Return an S3 GetObject-like response."""
            self.calls.append(kwargs)
            return {
                "Body": self.source_file,
                "ContentLength": len(self.source_file.content),
            }

    class DirectS3Storage(S3Storage):
        """S3 storage double that needs no network configuration."""

        def _normalize_name(self, name):
            """Return the expected media-prefixed object key."""
            return f"media/{name}"

        @property
        def connection(self):
            """Return the configured S3 client double."""
            return self._connection

    class S3Photo:
        """Photo-like field that fails if code tries a HeadObject-backed access."""

        name = "members/maria.png"

        def __init__(self, storage):
            """Attach the S3 storage double."""
            self.storage = storage

        def __bool__(self):
            """Indicate that a photo exists."""
            return True

        @property
        def size(self):
            """Fail if the helper attempts the HeadObject-backed size property."""
            raise AssertionError("S3 photos must not use the size property")

        def open(self, mode):
            """Fail if the helper attempts the HeadObject-backed open method."""
            raise AssertionError("S3 photos must not use the open method")

        def close(self):
            """Mirror Django file field close behavior."""

    source_file = SourceFile(_image_upload().read())
    client = S3Client(source_file)
    storage = object.__new__(DirectS3Storage)
    storage.bucket_name = "mdc-media"
    storage._connection = SimpleNamespace(meta=SimpleNamespace(client=client))
    member = SimpleNamespace(
        name="Maria Silva",
        birthday_occurrence=date(2026, 7, 22),
        photo=S3Photo(storage),
    )

    entry = images.build_birthday_image_entries([member])[0]

    assert entry["photo_data_url"].startswith("data:image/jpeg;base64,")
    assert client.calls == [
        {
            "Bucket": "mdc-media",
            "Key": "media/members/maria.png",
        }
    ]
    assert source_file.closed is True


def test_birthday_image_entries_use_default_photo_for_large_sources():
    """Birthday report entries should skip source photos above the safe size."""

    class LargePhoto:
        """Photo-like object that should not be opened because it is too large."""

        name = "large.jpg"
        size = images.BIRTHDAY_PHOTO_MAX_SOURCE_SIZE + 1

        def __bool__(self):
            """Return true so the helper treats this as an existing photo."""
            return True

        def open(self, mode):
            """Fail if the helper tries to open an oversized source."""
            raise AssertionError("Large photos should not be opened")

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
