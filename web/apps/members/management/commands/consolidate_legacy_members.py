"""Generate reviewed Django fixture artifacts from approved legacy sources."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.members.legacy_import.pipeline import (
    ConsolidationError,
    consolidate_legacy_members,
)


class Command(BaseCommand):
    """Consolidate legacy XLSX and PDFs without writing to the database."""

    help = "Generate a reviewable member fixture, reports, and staged photos."

    def add_arguments(self, parser):
        """Define explicit sources, deterministic identifiers, and output path."""
        parser.add_argument("--spreadsheet", required=True, type=Path)
        parser.add_argument("--pdf-dir", required=True, type=Path)
        parser.add_argument("--output-dir", required=True, type=Path)
        parser.add_argument("--pk-base", required=True, type=int)
        parser.add_argument("--snapshot-timestamp")

    def handle(self, *args, **options):
        """Run consolidation and print only aggregate, non-PII results."""
        try:
            result = consolidate_legacy_members(
                spreadsheet_path=options["spreadsheet"],
                pdf_directory=options["pdf_dir"],
                output_directory=options["output_dir"],
                pk_base=options["pk_base"],
                snapshot_timestamp=options["snapshot_timestamp"],
            )
        except ConsolidationError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            "Legacy member consolidation summary: "
            + " ".join(
                f"{name}={value}" for name, value in result.summary.items()
            )
        )
        self.stdout.write(f"Artifacts: {result.fixture_path.parent}")
