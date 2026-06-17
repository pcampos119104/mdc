"""Reusable base models and managers for the members app."""

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet with soft delete helpers for records kept in the database."""

    def alive(self):
        """Return records that were not soft deleted."""
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        """Return records that were soft deleted."""
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        """Soft delete records in this queryset."""
        now = timezone.now()
        update_values = {"deleted_at": now}

        if any(field.name == "updated_at" for field in self.model._meta.fields):
            update_values["updated_at"] = now

        count = self.alive().update(**update_values)
        return count, {self.model._meta.label: count}

    def hard_delete(self):
        """Permanently delete records in this queryset."""
        return super().delete()


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager that hides soft-deleted records."""

    def get_queryset(self):
        """Return only records that were not soft deleted."""
        return super().get_queryset().alive()


class SoftDeleteModel(models.Model):
    """Abstract base model for records that should be removed logically."""

    deleted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Data e hora em que o registro foi removido logicamente.",
    )

    objects = SoftDeleteManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """Soft delete this record without removing it from the database."""
        if self.pk is None:
            raise ValueError("Cannot soft delete an unsaved object.")

        if self.deleted_at is not None:
            return 0, {self._meta.label: 0}

        self.deleted_at = timezone.now()
        update_fields = ["deleted_at"]

        if any(field.name == "updated_at" for field in self._meta.fields):
            update_fields.append("updated_at")

        self.save(using=using, update_fields=update_fields)
        return 1, {self._meta.label: 1}

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete this record from the database."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self, using=None):
        """Restore a previously soft-deleted record."""
        if self.pk is None:
            raise ValueError("Cannot restore an unsaved object.")

        if self.deleted_at is None:
            return 0, {self._meta.label: 0}

        self.deleted_at = None
        update_fields = ["deleted_at"]

        if any(field.name == "updated_at" for field in self._meta.fields):
            update_fields.append("updated_at")

        self.save(using=using, update_fields=update_fields)
        return 1, {self._meta.label: 1}
