"""Upload validated member photos after loading the approved legacy fixture."""

import hashlib
import hmac
import json
import os
import re
import stat
import tempfile
import unicodedata
from datetime import date
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image

from apps.members.models import Member


MAX_PHOTO_DIMENSION = 512
MAX_PHOTO_BYTES = 5 * 1024 * 1024
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class EntryFailure(Exception):
    """Mark a manifest entry that cannot be safely uploaded."""

    def __init__(self, reason_code):
        """Store a stable, non-sensitive reason for the entry failure."""
        self.reason_code = reason_code
        super().__init__(reason_code)


class ExistingPhotoConflict(EntryFailure):
    """Mark an existing different member photo skipped without replacement."""

    def __init__(self):
        """Use the stable reason assigned to default photo conflicts."""
        super().__init__("existing_photo_conflict")


def _load_entries(manifest_path):
    """Load photo entries from a supported JSON manifest shape."""
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CommandError("Unable to read a valid legacy photo manifest.") from exc

    entries = payload.get("photos") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise CommandError("The legacy photo manifest must contain a photos array.")

    return entries


def _normalize_name(value):
    """Normalize a name while retaining exact letters and diacritics."""
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _validate_identity(entry, member):
    """Verify the manifest identity against the selected member."""
    identity = entry.get("expected_identity")
    if not isinstance(identity, dict):
        raise EntryFailure("invalid_expected_identity")

    expected_name = identity.get("name")
    if not isinstance(expected_name, str) or not expected_name.strip():
        raise EntryFailure("invalid_expected_identity")
    if _normalize_name(expected_name) != _normalize_name(member.name):
        raise EntryFailure("identity_name_mismatch")

    if "birth_date" not in identity or "cpf" not in identity:
        raise EntryFailure("invalid_expected_identity")

    expected_birth_date = identity["birth_date"]
    if expected_birth_date is None:
        if member.birth_date is not None:
            raise EntryFailure("identity_birth_date_mismatch")
    else:
        if not isinstance(expected_birth_date, str):
            raise EntryFailure("invalid_expected_identity")
        try:
            parsed_birth_date = date.fromisoformat(expected_birth_date)
        except ValueError as exc:
            raise EntryFailure("invalid_expected_identity") from exc
        if parsed_birth_date.isoformat() != expected_birth_date:
            raise EntryFailure("invalid_expected_identity")
        if member.birth_date != parsed_birth_date:
            raise EntryFailure("identity_birth_date_mismatch")

    expected_cpf = identity["cpf"]
    if expected_cpf is None:
        if member.cpf:
            raise EntryFailure("identity_cpf_mismatch")
    else:
        if not isinstance(expected_cpf, str) or not expected_cpf:
            raise EntryFailure("invalid_expected_identity")
        if member.cpf != expected_cpf:
            raise EntryFailure("identity_cpf_mismatch")


def _validated_photo(entry, photos_dir):
    """Return validated JPEG bytes and their declared SHA256 digest."""
    photo_file = entry.get("photo_file")
    if not isinstance(photo_file, str) or not photo_file:
        raise EntryFailure("invalid_photo_path")

    relative_path = Path(photo_file)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise EntryFailure("photo_path_traversal")

    photo_path = (photos_dir / relative_path).resolve()
    try:
        photo_path.relative_to(photos_dir)
    except ValueError as exc:
        raise EntryFailure("photo_path_traversal") from exc

    if not photo_path.is_file():
        raise EntryFailure("photo_file_unavailable")

    declared_byte_size = entry.get("byte_size")
    if (
        isinstance(declared_byte_size, bool)
        or not isinstance(declared_byte_size, int)
        or declared_byte_size <= 0
    ):
        raise EntryFailure("invalid_byte_size")
    if declared_byte_size > MAX_PHOTO_BYTES:
        raise EntryFailure("photo_file_too_large")

    try:
        actual_byte_size = photo_path.stat().st_size
    except OSError as exc:
        raise EntryFailure("photo_file_unavailable") from exc
    if actual_byte_size > MAX_PHOTO_BYTES:
        raise EntryFailure("photo_file_too_large")
    if actual_byte_size != declared_byte_size:
        raise EntryFailure("byte_size_mismatch")

    declared_sha256 = entry.get("sha256")
    if not isinstance(declared_sha256, str) or not SHA256_PATTERN.fullmatch(
        declared_sha256
    ):
        raise EntryFailure("invalid_sha256")
    declared_sha256 = declared_sha256.lower()

    try:
        photo_bytes = photo_path.read_bytes()
    except OSError as exc:
        raise EntryFailure("photo_file_unavailable") from exc
    if len(photo_bytes) != declared_byte_size:
        raise EntryFailure("byte_size_mismatch")

    actual_sha256 = hashlib.sha256(photo_bytes).hexdigest()
    if not hmac.compare_digest(actual_sha256, declared_sha256):
        raise EntryFailure("sha256_mismatch")

    try:
        with Image.open(BytesIO(photo_bytes)) as image:
            if image.format != "JPEG":
                raise EntryFailure("invalid_jpeg")
            if max(image.size) > MAX_PHOTO_DIMENSION:
                raise EntryFailure("photo_dimensions_exceeded")
            image.verify()
        with Image.open(BytesIO(photo_bytes)) as image:
            image.load()
    except (OSError, SyntaxError, ValueError) as exc:
        raise EntryFailure("invalid_jpeg") from exc

    return photo_bytes, declared_sha256


def _storage_file_matches(storage, target_name, expected_sha256):
    """Return whether an existing storage object has the expected digest."""
    digest = hashlib.sha256()
    with storage.open(target_name, "rb") as stored_file:
        while chunk := stored_file.read(1024 * 1024):
            digest.update(chunk)
    return hmac.compare_digest(digest.hexdigest(), expected_sha256)


def _cleanup_storage_file(storage, name):
    """Delete a newly written object and report whether it is now absent."""
    try:
        storage.delete(name)
        return not storage.exists(name)
    except Exception:
        return False


def _stage_photo(storage, target_name, photo_bytes, expected_sha256):
    """Ensure validated bytes exist at the deterministic storage target."""
    try:
        if storage.exists(target_name):
            if not _storage_file_matches(storage, target_name, expected_sha256):
                raise EntryFailure("storage_hash_mismatch")
            return False

        try:
            saved_name = storage.save(target_name, ContentFile(photo_bytes))
        except Exception as exc:
            raise EntryFailure("storage_save_failed_possible_orphan") from exc
        if saved_name == target_name:
            return True

        if not _cleanup_storage_file(storage, saved_name):
            raise EntryFailure("storage_renamed_output_cleanup_failed")
        if storage.exists(target_name) and _storage_file_matches(
            storage, target_name, expected_sha256
        ):
            return False
        raise EntryFailure("storage_target_conflict")
    except EntryFailure:
        raise
    except Exception as exc:
        raise EntryFailure("storage_error") from exc


def _valid_member_pk(entry):
    """Return a positive integer member PK when an entry provides one."""
    if not isinstance(entry, dict):
        return None
    member_pk = entry.get("member_pk")
    if isinstance(member_pk, bool) or not isinstance(member_pk, int):
        return None
    return member_pk if member_pk > 0 else None


def _audit_result(entry, outcome, reason_code=None):
    """Build one non-sensitive audit result in manifest order."""
    input_status = entry.get("status") if isinstance(entry, dict) else None
    result = {
        "input_status": input_status if isinstance(input_status, str) else None,
        "outcome": outcome,
    }
    member_pk = _valid_member_pk(entry)
    if member_pk is not None:
        result["member_pk"] = member_pk
    if reason_code is not None:
        result["reason_code"] = reason_code
    return result


def _ensure_safe_report_target(report_path, manifest_path):
    """Reject report destinations that could overwrite or follow unsafe paths."""
    if not report_path.name:
        raise CommandError("The audit report path must name a file.")

    try:
        report_parent = report_path.parent.resolve(strict=True)
    except OSError as exc:
        raise CommandError("The audit report directory is unavailable.") from exc
    if not report_parent.is_dir():
        raise CommandError("The audit report parent must be a directory.")

    safe_report_path = report_parent / report_path.name
    try:
        if safe_report_path.resolve(strict=False) == manifest_path.resolve(
            strict=False
        ):
            raise CommandError("The audit report cannot replace the manifest.")
        report_mode = safe_report_path.lstat().st_mode
    except FileNotFoundError:
        return safe_report_path
    except OSError as exc:
        raise CommandError("The audit report path is unavailable.") from exc

    if not stat.S_ISREG(report_mode):
        raise CommandError("The audit report path must be a regular file.")
    return safe_report_path


def _ensure_report_outside_photos(report_path, photos_dir, entries):
    """Reject reports that could replace staged photo inputs."""
    try:
        report_path.relative_to(photos_dir)
    except ValueError:
        pass
    else:
        raise CommandError("The audit report must be outside the photos directory.")

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        photo_file = entry.get("photo_file")
        if not isinstance(photo_file, str) or not photo_file:
            continue
        relative_path = Path(photo_file)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            continue
        try:
            photo_path = (photos_dir / relative_path).resolve(strict=False)
            same_file = (
                report_path.exists()
                and photo_path.exists()
                and report_path.samefile(photo_path)
            )
        except OSError as exc:
            raise CommandError("Unable to validate the audit report path.") from exc
        if report_path == photo_path or same_file:
            raise CommandError("The audit report cannot replace a staged photo.")


def _write_audit_report(
    report_path,
    manifest_path,
    photos_path,
    entries,
    counts,
    results,
):
    """Atomically write a deterministic private audit report."""
    _ensure_report_outside_photos(report_path, photos_path, entries)
    report_path = _ensure_safe_report_target(report_path, manifest_path)
    report_content = json.dumps(
        {
            "counts": counts,
            "results": results,
            "schema_version": 1,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    file_descriptor = None
    temporary_path = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=report_path.parent,
            prefix=".legacy-photo-report-",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        os.fchmod(file_descriptor, 0o600)
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as file:
            file_descriptor = None
            file.write(report_content)
            file.flush()
            os.fsync(file.fileno())

        _ensure_safe_report_target(report_path, manifest_path)
        os.replace(temporary_path, report_path)
        temporary_path = None
    except CommandError:
        raise
    except OSError as exc:
        raise CommandError("Unable to write the audit report safely.") from exc
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass


class Command(BaseCommand):
    """Upload approved legacy member photos from a post-loaddata manifest."""

    help = "Upload validated member photos after loading the approved legacy fixture."

    def add_arguments(self, parser):
        """Define manifest, local photo directory, and write-control options."""
        parser.add_argument("--manifest", required=True, type=Path)
        parser.add_argument("--photos-dir", required=True, type=Path)
        parser.add_argument("--report", type=Path)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--replace", action="store_true")

    def handle(self, *args, **options):
        """Validate every ready entry and upload safe photos independently."""
        manifest_path = Path(options["manifest"])
        report_option = options.get("report")
        report_path = (
            Path(report_option)
            if report_option
            else manifest_path.parent / "photo_upload_report.json"
        )
        report_path = _ensure_safe_report_target(report_path, manifest_path)
        photos_option = Path(options["photos_dir"])
        try:
            photos_path = photos_option.resolve(strict=False)
        except OSError as exc:
            raise CommandError(
                "Unable to establish safe audit report separation."
            ) from exc
        _ensure_report_outside_photos(report_path, photos_path, [])

        counts = {
            "ready": 0,
            "ignored": 0,
            "uploaded": 0,
            "updated": 0,
            "unchanged": 0,
            "dry_run": 0,
            "skipped": 0,
            "failures": 0,
        }
        results = []

        try:
            entries = _load_entries(manifest_path)
        except CommandError:
            _write_audit_report(
                report_path,
                manifest_path,
                photos_path,
                [],
                counts,
                results,
            )
            raise

        _ensure_report_outside_photos(report_path, photos_path, entries)
        try:
            photos_dir = photos_option.resolve(strict=True)
        except OSError as exc:
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("status") != "ready":
                    counts["ignored"] += 1
                    results.append(_audit_result(entry, "ignored"))
                    continue
                counts["ready"] += 1
                counts["failures"] += 1
                results.append(
                    _audit_result(
                        entry,
                        "failed",
                        "photos_directory_unavailable",
                    )
                )
            _write_audit_report(
                report_path,
                manifest_path,
                photos_path,
                entries,
                counts,
                results,
            )
            self._write_summary(counts)
            raise CommandError("The legacy photos directory is unavailable.") from exc
        if not photos_dir.is_dir():
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("status") != "ready":
                    counts["ignored"] += 1
                    results.append(_audit_result(entry, "ignored"))
                    continue
                counts["ready"] += 1
                counts["failures"] += 1
                results.append(
                    _audit_result(
                        entry,
                        "failed",
                        "photos_directory_unavailable",
                    )
                )
            _write_audit_report(
                report_path,
                manifest_path,
                photos_path,
                entries,
                counts,
                results,
            )
            self._write_summary(counts)
            raise CommandError("The legacy photos path must be a directory.")

        _ensure_report_outside_photos(report_path, photos_dir, entries)

        for entry in entries:
            if not isinstance(entry, dict) or entry.get("status") != "ready":
                counts["ignored"] += 1
                results.append(_audit_result(entry, "ignored"))
                continue

            counts["ready"] += 1
            try:
                outcomes = self._process_entry(
                    entry,
                    photos_dir,
                    dry_run=options["dry_run"],
                    replace=options["replace"],
                )
            except ExistingPhotoConflict as exc:
                counts["skipped"] += 1
                counts["failures"] += 1
                results.append(_audit_result(entry, "skipped", exc.reason_code))
                continue
            except EntryFailure as exc:
                counts["failures"] += 1
                results.append(_audit_result(entry, "failed", exc.reason_code))
                continue
            except Exception:
                counts["failures"] += 1
                results.append(_audit_result(entry, "failed", "unexpected_error"))
                continue

            for outcome in outcomes:
                counts[outcome] += 1
            if "dry_run" in outcomes:
                audit_outcome = "dry_run"
            elif "uploaded" in outcomes:
                audit_outcome = "uploaded"
            elif "updated" in outcomes:
                audit_outcome = "updated"
            else:
                audit_outcome = "unchanged"
            results.append(_audit_result(entry, audit_outcome))

        _write_audit_report(
            report_path,
            manifest_path,
            photos_dir,
            entries,
            counts,
            results,
        )
        self._write_summary(counts)
        if counts["failures"]:
            raise CommandError(
                f"Legacy photo upload completed with {counts['failures']} failure(s)."
            )

    def _write_summary(self, counts):
        """Print only aggregate, non-sensitive uploader counts."""
        self.stdout.write(
            "Legacy photo upload summary: "
            + " ".join(f"{name}={value}" for name, value in counts.items())
        )

    def _process_entry(self, entry, photos_dir, *, dry_run, replace):
        """Validate and, unless simulated, stage and attach one member photo."""
        member_pk = _valid_member_pk(entry)
        if member_pk is None:
            raise EntryFailure("invalid_member_pk")

        try:
            member = Member.all_objects.filter(pk=member_pk).first()
        except (ValueError, TypeError) as exc:
            raise EntryFailure("invalid_member_pk") from exc
        if member is None:
            raise EntryFailure("member_not_found")

        _validate_identity(entry, member)
        photo_bytes, declared_sha256 = _validated_photo(entry, photos_dir)
        target_name = (
            f"members/legacy/{member.pk}-{declared_sha256[:12]}.jpg"
        )

        if dry_run:
            current_name = member.photo.name if member.photo else ""
            if current_name and current_name != target_name and not replace:
                raise ExistingPhotoConflict()
            return {"dry_run"}

        storage = None
        uploaded = False
        try:
            with transaction.atomic():
                locked_member = (
                    Member.all_objects.select_for_update()
                    .filter(pk=member_pk)
                    .first()
                )
                if locked_member is None:
                    raise EntryFailure("member_not_found")

                _validate_identity(entry, locked_member)
                current_name = (
                    locked_member.photo.name if locked_member.photo else ""
                )
                if current_name and current_name != target_name and not replace:
                    raise ExistingPhotoConflict()

                storage = locked_member.photo.storage
                uploaded = _stage_photo(
                    storage,
                    target_name,
                    photo_bytes,
                    declared_sha256,
                )
                outcomes = {"uploaded"} if uploaded else set()

                if current_name == target_name:
                    outcomes.add("unchanged")
                else:
                    locked_member.photo.name = target_name
                    locked_member.save(update_fields=["photo", "updated_at"])
                    outcomes.add("updated")
        except EntryFailure:
            raise
        except Exception as exc:
            reason_code = "database_update_failed"
            if uploaded and storage is not None:
                if not _cleanup_storage_file(storage, target_name):
                    reason_code = "database_update_failed_cleanup_failed"
            raise EntryFailure(reason_code) from exc

        return outcomes
