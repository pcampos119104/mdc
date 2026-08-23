"""Tests for the post-loaddata legacy member photo uploader."""

import hashlib
import json
import stat
from datetime import date
from io import BytesIO, StringIO
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from PIL import Image, ImageFile

from apps.members.management.commands import upload_legacy_member_photos as uploader
from apps.members.models import Member


def _jpeg_bytes(size=(120, 80), color=(35, 90, 160)):
    """Return a small valid JPEG for command tests."""
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="JPEG")
    return output.getvalue()


def _member():
    """Create a member with all supported legacy identity fields."""
    return Member.objects.create(
        name="Maria da Silva",
        birth_date=date(1985, 7, 14),
        cpf="12345678901",
    )


def _prepare_manifest(tmp_path, member, photo_bytes, **entry_overrides):
    """Write one photo and a matching object-shaped legacy manifest."""
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir(exist_ok=True)
    photo_path = photos_dir / "member.jpg"
    photo_path.write_bytes(photo_bytes)
    digest = hashlib.sha256(photo_bytes).hexdigest()
    entry = {
        "member_pk": member.pk,
        "photo_file": photo_path.name,
        "byte_size": len(photo_bytes),
        "sha256": digest,
        "expected_identity": {
            "name": "  maria   DA silva ",
            "birth_date": "1985-07-14",
            "cpf": "12345678901",
        },
        "status": "ready",
    }
    entry.update(entry_overrides)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"photos": [entry]}), encoding="utf-8")
    return manifest_path, photos_dir, digest


def _call_uploader(manifest_path, photos_dir, **options):
    """Run the uploader while capturing its aggregate standard output."""
    stdout = StringIO()
    call_command(
        "upload_legacy_member_photos",
        manifest=str(manifest_path),
        photos_dir=str(photos_dir),
        stdout=stdout,
        **options,
    )
    return stdout.getvalue()


def _read_report(manifest_path, report_path=None):
    """Return the parsed audit report and its resolved local path."""
    report_path = report_path or manifest_path.parent / "photo_upload_report.json"
    return json.loads(report_path.read_text(encoding="utf-8")), report_path


@pytest.mark.django_db
def test_upload_legacy_member_photo_succeeds(settings, tmp_path):
    """A validated ready entry should upload and attach its deterministic photo."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )

    stdout = _call_uploader(manifest_path, photos_dir)

    member.refresh_from_db()
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert member.photo.name == target_name
    assert (settings.MEDIA_ROOT / target_name).read_bytes() == photo_bytes
    assert "uploaded=1" in stdout
    assert "updated=1" in stdout
    assert "failures=0" in stdout
    assert member.name not in stdout
    report, report_path = _read_report(manifest_path)
    assert report["schema_version"] == 1
    assert report["counts"]["uploaded"] == 1
    assert report["counts"]["updated"] == 1
    assert report["counts"]["failures"] == 0
    assert report["results"] == [
        {
            "input_status": "ready",
            "member_pk": member.pk,
            "outcome": "uploaded",
        }
    ]
    assert stat.S_IMODE(report_path.stat().st_mode) == 0o600
    report_content = report_path.read_text(encoding="utf-8")
    assert member.name not in report_content
    assert member.cpf not in report_content
    assert str(tmp_path) not in report_content
    assert "member.jpg" not in report_content


@pytest.mark.django_db
def test_upload_legacy_member_photo_dry_run_does_not_write(settings, tmp_path):
    """Dry-run should validate without writing storage or the database."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )

    stdout = _call_uploader(manifest_path, photos_dir, dry_run=True)

    member.refresh_from_db()
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert not member.photo
    assert not (settings.MEDIA_ROOT / target_name).exists()
    assert "dry_run=1" in stdout
    assert "failures=0" in stdout
    report, _report_path = _read_report(manifest_path)
    assert report["counts"]["dry_run"] == 1
    assert report["results"] == [
        {
            "input_status": "ready",
            "member_pk": member.pk,
            "outcome": "dry_run",
        }
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("expected_identity", "reason_code"),
    [
        (
            {
                "name": "Maria da Silva",
                "birth_date": None,
                "cpf": "12345678901",
            },
            "identity_birth_date_mismatch",
        ),
        (
            {
                "name": "Maria da Silva",
                "birth_date": "1985-07-14",
                "cpf": None,
            },
            "identity_cpf_mismatch",
        ),
    ],
)
def test_upload_legacy_member_photo_treats_null_identity_as_assertion(
    settings, tmp_path, expected_identity, reason_code
):
    """Null birth date and CPF values should assert empty member values."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path,
        member,
        _jpeg_bytes(),
        expected_identity=expected_identity,
    )

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir, dry_run=True)

    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["outcome"] == "failed"
    assert report["results"][0]["reason_code"] == reason_code


@pytest.mark.django_db
def test_upload_legacy_member_photo_accepts_matching_null_identity(settings, tmp_path):
    """Null identity assertions should pass when member values are empty."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = Member.objects.create(name="Maria sem documentos")
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path,
        member,
        _jpeg_bytes(),
        expected_identity={
            "name": "Maria sem documentos",
            "birth_date": None,
            "cpf": None,
        },
    )

    _call_uploader(manifest_path, photos_dir, dry_run=True)

    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["outcome"] == "dry_run"


@pytest.mark.django_db
def test_upload_legacy_member_photo_rejects_identity_mismatch(settings, tmp_path):
    """A mismatched expected identity should fail without attaching a photo."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path,
        member,
        _jpeg_bytes(),
        expected_identity={
            "name": "Outra Pessoa",
            "birth_date": "1985-07-14",
            "cpf": "12345678901",
        },
    )
    stdout = StringIO()

    with pytest.raises(CommandError):
        call_command(
            "upload_legacy_member_photos",
            manifest=str(manifest_path),
            photos_dir=str(photos_dir),
            stdout=stdout,
        )

    member.refresh_from_db()
    assert not member.photo
    assert "failures=1" in stdout.getvalue()
    assert member.name not in stdout.getvalue()
    report, _report_path = _read_report(manifest_path)
    assert report["counts"]["failures"] == 1
    assert report["results"] == [
        {
            "input_status": "ready",
            "member_pk": member.pk,
            "outcome": "failed",
            "reason_code": "identity_name_mismatch",
        }
    ]


@pytest.mark.django_db
def test_upload_legacy_member_photo_rejects_hash_mismatch(settings, tmp_path):
    """A local file whose digest differs from the manifest should fail."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path,
        member,
        _jpeg_bytes(),
        sha256="0" * 64,
    )
    stdout = StringIO()

    with pytest.raises(CommandError):
        call_command(
            "upload_legacy_member_photos",
            manifest=str(manifest_path),
            photos_dir=str(photos_dir),
            stdout=stdout,
        )

    member.refresh_from_db()
    assert not member.photo
    assert "failures=1" in stdout.getvalue()
    report, _report_path = _read_report(manifest_path)
    assert report["results"] == [
        {
            "input_status": "ready",
            "member_pk": member.pk,
            "outcome": "failed",
            "reason_code": "sha256_mismatch",
        }
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("byte_size", "reason_code"),
    [
        (None, "invalid_byte_size"),
        (0, "invalid_byte_size"),
        (-1, "invalid_byte_size"),
        (True, "invalid_byte_size"),
        ("100", "invalid_byte_size"),
        (uploader.MAX_PHOTO_BYTES + 1, "photo_file_too_large"),
    ],
)
def test_upload_legacy_member_photo_rejects_invalid_declared_byte_size(
    settings, tmp_path, byte_size, reason_code
):
    """Manifest byte size should be a strictly positive integer."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path,
        member,
        _jpeg_bytes(),
        byte_size=byte_size,
    )

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["reason_code"] == reason_code


@pytest.mark.django_db
def test_upload_legacy_member_photo_rejects_oversize_before_read(
    settings, tmp_path, monkeypatch
):
    """An oversized staged file should be rejected from stat data without reading."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    oversized_content = b"x" * (uploader.MAX_PHOTO_BYTES + 1)
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path,
        member,
        oversized_content,
        byte_size=uploader.MAX_PHOTO_BYTES,
    )

    def unexpected_read(path):
        """Fail if validation reads content already known to be oversized."""
        raise AssertionError("oversized photo should not be read")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["reason_code"] == "photo_file_too_large"


@pytest.mark.django_db
def test_upload_legacy_member_photo_rejects_trailing_payload_before_read(
    settings, tmp_path, monkeypatch
):
    """A file larger than its manifest size should fail before content is read."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )
    photo_path = photos_dir / "member.jpg"
    photo_path.write_bytes(photo_bytes + b"trailing-payload")

    def unexpected_read(path):
        """Fail if a stat size mismatch reaches content reading."""
        raise AssertionError("size-mismatched photo should not be read")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["reason_code"] == "byte_size_mismatch"


@pytest.mark.django_db
def test_upload_legacy_member_photo_rejects_path_traversal(settings, tmp_path):
    """A manifest photo path may not traverse outside the photo directory."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path,
        member,
        photo_bytes,
        photo_file="../outside.jpg",
    )
    (tmp_path / "outside.jpg").write_bytes(photo_bytes)

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    member.refresh_from_db()
    assert not member.photo
    report, _report_path = _read_report(manifest_path)
    assert report["results"] == [
        {
            "input_status": "ready",
            "member_pk": member.pk,
            "outcome": "failed",
            "reason_code": "photo_path_traversal",
        }
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("report_name", ["audit.json", "member.jpg"])
def test_upload_legacy_member_photo_rejects_reports_inside_photos(
    settings, tmp_path, report_name
):
    """A report must never replace or be created among staged photo inputs."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )
    report_path = photos_dir / report_name

    with pytest.raises(CommandError):
        _call_uploader(
            manifest_path,
            photos_dir,
            report=str(report_path),
        )

    member.refresh_from_db()
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert not member.photo
    assert not (settings.MEDIA_ROOT / target_name).exists()
    assert (photos_dir / "member.jpg").read_bytes() == photo_bytes
    if report_name != "member.jpg":
        assert not report_path.exists()


def test_upload_legacy_member_photo_protects_photo_on_malformed_manifest(tmp_path):
    """A malformed manifest error report must not replace a staged JPEG."""
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    photo_path = photos_dir / "member.jpg"
    photo_bytes = _jpeg_bytes()
    photo_path.write_bytes(photo_bytes)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{", encoding="utf-8")

    with pytest.raises(CommandError):
        _call_uploader(
            manifest_path,
            photos_dir,
            report=str(photo_path),
        )

    assert photo_path.read_bytes() == photo_bytes


@pytest.mark.django_db
@pytest.mark.parametrize("photos_path_kind", ["unavailable", "not_directory"])
def test_upload_legacy_member_photo_protects_report_target_on_invalid_photos_path(
    settings, tmp_path, photos_path_kind
):
    """Invalid photos paths must be separated from reports before error writes."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, valid_photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )
    if photos_path_kind == "not_directory":
        invalid_photos_path = valid_photos_dir / "member.jpg"
        original_content = invalid_photos_path.read_bytes()
    else:
        invalid_photos_path = tmp_path / "missing-staged-photo.jpg"
        original_content = None

    with pytest.raises(CommandError):
        _call_uploader(
            manifest_path,
            invalid_photos_path,
            report=str(invalid_photos_path),
        )

    if original_content is None:
        assert not invalid_photos_path.exists()
    else:
        assert invalid_photos_path.read_bytes() == original_content
    member.refresh_from_db()
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert not member.photo
    assert not (settings.MEDIA_ROOT / target_name).exists()


@pytest.mark.django_db
def test_upload_legacy_member_photo_skips_existing_photo_by_default(
    settings, tmp_path
):
    """An existing different member photo should be a default conflict."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    storage = member.photo.storage
    old_name = storage.save("members/existing.jpg", ContentFile(b"old-photo"))
    Member.all_objects.filter(pk=member.pk).update(photo=old_name)
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, _jpeg_bytes()
    )
    stdout = StringIO()

    with pytest.raises(CommandError):
        call_command(
            "upload_legacy_member_photos",
            manifest=str(manifest_path),
            photos_dir=str(photos_dir),
            stdout=stdout,
        )

    member.refresh_from_db()
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert member.photo.name == old_name
    assert storage.exists(old_name)
    assert not storage.exists(target_name)
    assert "skipped=1" in stdout.getvalue()
    assert "failures=1" in stdout.getvalue()
    report, _report_path = _read_report(manifest_path)
    assert report["results"] == [
        {
            "input_status": "ready",
            "member_pk": member.pk,
            "outcome": "skipped",
            "reason_code": "existing_photo_conflict",
        }
    ]


@pytest.mark.django_db
def test_upload_legacy_member_photo_is_idempotent_for_exact_target(
    settings, tmp_path
):
    """An exact valid target should not be uploaded or updated again."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    storage = member.photo.storage
    assert storage.save(target_name, ContentFile(photo_bytes)) == target_name
    Member.all_objects.filter(pk=member.pk).update(photo=target_name)
    member.refresh_from_db()
    previous_updated_at = member.updated_at

    stdout = _call_uploader(manifest_path, photos_dir)

    member.refresh_from_db()
    assert member.photo.name == target_name
    assert member.updated_at == previous_updated_at
    assert storage.exists(target_name)
    assert "uploaded=0" in stdout
    assert "updated=0" in stdout
    assert "unchanged=1" in stdout
    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["outcome"] == "unchanged"


@pytest.mark.django_db
def test_upload_legacy_member_photo_replace_preserves_old_storage(
    settings, tmp_path
):
    """Replace should change only the pointer and retain the old storage object."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    storage = member.photo.storage
    old_name = storage.save("members/existing.jpg", ContentFile(b"old-photo"))
    Member.all_objects.filter(pk=member.pk).update(photo=old_name)
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )

    stdout = _call_uploader(manifest_path, photos_dir, replace=True)

    member.refresh_from_db()
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert member.photo.name == target_name
    assert storage.exists(old_name)
    assert storage.exists(target_name)
    assert "uploaded=1" in stdout
    assert "updated=1" in stdout
    assert "failures=0" in stdout
    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["outcome"] == "uploaded"


@pytest.mark.django_db
def test_upload_legacy_member_photo_revalidates_locked_member(
    settings, tmp_path, monkeypatch
):
    """A member changed after local validation should fail locked revalidation."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )
    original_validation = uploader._validated_photo

    def mutate_after_local_validation(entry, directory):
        """Change identity after the initial member check but before locking."""
        result = original_validation(entry, directory)
        Member.all_objects.filter(pk=member.pk).update(cpf="10987654321")
        return result

    monkeypatch.setattr(uploader, "_validated_photo", mutate_after_local_validation)

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert not (settings.MEDIA_ROOT / target_name).exists()
    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["reason_code"] == "identity_cpf_mismatch"


@pytest.mark.django_db
def test_upload_legacy_member_photo_rechecks_locked_photo_policy(
    settings, tmp_path, monkeypatch
):
    """A photo pointer changed before locking should trigger default conflict policy."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )
    original_validation = uploader._validated_photo
    raced_photo_name = "members/raced-photo.jpg"

    def add_photo_after_local_validation(entry, directory):
        """Set a competing photo pointer before the command locks the member."""
        result = original_validation(entry, directory)
        Member.all_objects.filter(pk=member.pk).update(photo=raced_photo_name)
        return result

    monkeypatch.setattr(uploader, "_validated_photo", add_photo_after_local_validation)

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    member.refresh_from_db()
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert member.photo.name == raced_photo_name
    assert not (settings.MEDIA_ROOT / target_name).exists()
    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["outcome"] == "skipped"
    assert report["results"][0]["reason_code"] == "existing_photo_conflict"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("cleanup_succeeds", "reason_code", "target_remains"),
    [
        (True, "database_update_failed", False),
        (False, "database_update_failed_cleanup_failed", True),
    ],
)
def test_upload_legacy_member_photo_reports_database_cleanup_status(
    settings,
    tmp_path,
    monkeypatch,
    cleanup_succeeds,
    reason_code,
    target_remains,
):
    """Database failures should audit whether uploaded object cleanup succeeded."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )
    original_save = Member.save

    def fail_photo_update(instance, *args, **kwargs):
        """Fail only the command's final member photo update."""
        if kwargs.get("update_fields") == ["photo", "updated_at"]:
            raise RuntimeError("database failure")
        return original_save(instance, *args, **kwargs)

    monkeypatch.setattr(Member, "save", fail_photo_update)
    if not cleanup_succeeds:
        monkeypatch.setattr(
            uploader,
            "_cleanup_storage_file",
            lambda storage, name: False,
        )

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    member.refresh_from_db()
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert not member.photo
    assert (settings.MEDIA_ROOT / target_name).exists() is target_remains
    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["reason_code"] == reason_code


@pytest.mark.django_db
def test_upload_legacy_member_photo_reports_renamed_output_cleanup_failure(
    settings, tmp_path, monkeypatch
):
    """A storage-renamed object that cannot be removed should fail distinctly."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path, member, _jpeg_bytes()
    )
    renamed_name = f"members/legacy/unexpected-{member.pk}.jpg"
    original_save = FileSystemStorage.save

    def save_with_unexpected_name(storage, name, content, max_length=None):
        """Simulate storage returning an unexpected available name."""
        return original_save(
            storage,
            renamed_name,
            content,
            max_length=max_length,
        )

    monkeypatch.setattr(FileSystemStorage, "save", save_with_unexpected_name)
    monkeypatch.setattr(
        uploader,
        "_cleanup_storage_file",
        lambda storage, name: False,
    )

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    member.refresh_from_db()
    assert not member.photo
    assert (settings.MEDIA_ROOT / renamed_name).exists()
    report, _report_path = _read_report(manifest_path)
    assert (
        report["results"][0]["reason_code"]
        == "storage_renamed_output_cleanup_failed"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("commit_before_error", "target_remains"),
    [
        (True, True),
        (False, False),
    ],
)
def test_upload_legacy_member_photo_reconciles_storage_save_exceptions(
    settings,
    tmp_path,
    monkeypatch,
    commit_before_error,
    target_remains,
):
    """Storage save exceptions should retain any possibly committed target."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )
    original_save = FileSystemStorage.save

    def fail_storage_save(storage, name, content, max_length=None):
        """Optionally commit the deterministic target before raising."""
        if commit_before_error:
            original_save(
                storage,
                name,
                content,
                max_length=max_length,
            )
        raise RuntimeError("storage save failure")

    monkeypatch.setattr(FileSystemStorage, "save", fail_storage_save)

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    member.refresh_from_db()
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert not member.photo
    assert (settings.MEDIA_ROOT / target_name).exists() is target_remains
    report, _report_path = _read_report(manifest_path)
    assert (
        report["results"][0]["reason_code"]
        == "storage_save_failed_possible_orphan"
    )


@pytest.mark.django_db
def test_upload_legacy_member_photo_never_deletes_false_negative_target(
    settings, tmp_path, monkeypatch
):
    """A false-negative existence check must not grant cleanup ownership."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    photo_bytes = _jpeg_bytes()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, photo_bytes
    )
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    storage = member.photo.storage
    assert storage.save(target_name, ContentFile(photo_bytes)) == target_name
    original_exists = FileSystemStorage.exists
    exists_checks = 0

    def false_negative_once(storage_backend, name):
        """Hide the pre-existing target from the initial idempotency check."""
        nonlocal exists_checks
        if name == target_name and exists_checks == 0:
            exists_checks += 1
            return False
        return original_exists(storage_backend, name)

    def fail_storage_save(storage_backend, name, content, max_length=None):
        """Fail without proving whether storage committed an object."""
        raise RuntimeError("storage save failure")

    monkeypatch.setattr(FileSystemStorage, "exists", false_negative_once)
    monkeypatch.setattr(FileSystemStorage, "save", fail_storage_save)

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    member.refresh_from_db()
    assert not member.photo
    assert (settings.MEDIA_ROOT / target_name).read_bytes() == photo_bytes
    report, _report_path = _read_report(manifest_path)
    assert (
        report["results"][0]["reason_code"]
        == "storage_save_failed_possible_orphan"
    )


@pytest.mark.django_db
def test_upload_legacy_member_photo_rejects_oversized_jpeg_before_verify(
    settings, tmp_path, monkeypatch
):
    """Oversized JPEG headers should fail before Pillow verifies image data."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path,
        member,
        _jpeg_bytes(size=(513, 1)),
    )

    def unexpected_verify(image):
        """Fail if oversized validation reaches decompression verification."""
        raise AssertionError("verify should not run")

    monkeypatch.setattr(ImageFile.ImageFile, "verify", unexpected_verify)

    with pytest.raises(CommandError):
        _call_uploader(manifest_path, photos_dir)

    report, _report_path = _read_report(manifest_path)
    assert report["results"][0]["reason_code"] == "photo_dimensions_exceeded"


@pytest.mark.django_db
def test_upload_legacy_member_photo_replaces_custom_report_deterministically(
    settings, tmp_path
):
    """A custom regular report should be privately and deterministically replaced."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    manifest_path, photos_dir, _digest = _prepare_manifest(
        tmp_path, member, _jpeg_bytes()
    )
    report_path = tmp_path / "custom-report.json"
    report_path.write_text("old report", encoding="utf-8")
    report_path.chmod(0o644)

    _call_uploader(
        manifest_path,
        photos_dir,
        dry_run=True,
        report=str(report_path),
    )
    first_content = report_path.read_bytes()
    _call_uploader(
        manifest_path,
        photos_dir,
        dry_run=True,
        report=str(report_path),
    )

    report, resolved_report_path = _read_report(manifest_path, report_path)
    assert report_path.read_bytes() == first_content
    assert report["results"][0]["outcome"] == "dry_run"
    assert stat.S_IMODE(resolved_report_path.stat().st_mode) == 0o600
    assert not (manifest_path.parent / "photo_upload_report.json").exists()
    member.refresh_from_db()
    assert not member.photo


@pytest.mark.django_db
def test_upload_legacy_member_photo_rejects_unsafe_report_paths(settings, tmp_path):
    """Unsafe report symlinks and unavailable parents should fail before writes."""
    settings.MEDIA_ROOT = tmp_path / "media"
    member = _member()
    manifest_path, photos_dir, digest = _prepare_manifest(
        tmp_path, member, _jpeg_bytes()
    )
    protected_path = tmp_path / "protected.json"
    protected_path.write_text("protected", encoding="utf-8")
    symlink_path = tmp_path / "report-link.json"
    symlink_path.symlink_to(protected_path)

    with pytest.raises(CommandError):
        _call_uploader(
            manifest_path,
            photos_dir,
            report=str(symlink_path),
        )
    with pytest.raises(CommandError):
        _call_uploader(
            manifest_path,
            photos_dir,
            report=str(tmp_path / "missing" / "report.json"),
        )

    member.refresh_from_db()
    target_name = f"members/legacy/{member.pk}-{digest[:12]}.jpg"
    assert not member.photo
    assert not (settings.MEDIA_ROOT / target_name).exists()
    assert protected_path.read_text(encoding="utf-8") == "protected"
