---
name: django-models
description: Use when creating or refactoring Django models, fields, relationships, choices, validators, managers, migrations, and model tests in this project.
---

# Django Models

## Scope

Use this skill when creating or refactoring Django models, model fields, relationships, model-level validation, managers, querysets, migrations, and model tests.

Follow `AGENTS.md` for project-wide rules. Keep models simple, explicit, idiomatic Django, and avoid premature abstractions.

## Field Selection Guide

Choose fields by data semantics, not by display format.

Use Django built-in fields before adding dependencies or custom fields.

Use `CharField` for short text and identifiers/codes that are made of digits but are not used for arithmetic.

Use `CharField` with validators for values where leading zeros matter, including CPF, CEP, and phone numbers.

Use `EmailField` for email addresses.

Use `DateField` for dates and `DateTimeField` for timestamps.

Use `BooleanField` for true/false values.

Use numeric fields only for values that are actually numbers for arithmetic, ranges, or quantities.

For this project, CPF should be stored as 11 digits in a `CharField`, validated as numeric, and unique when present.

For this project, CEP should be stored as 8 digits in a `CharField`, validated as numeric, preserving leading zeros.

For this project, phone numbers should be stored as digits in a `CharField`, validated as numeric, preserving leading zeros.

## Null and Blank Rules

`null` controls database storage. `blank` controls validation/forms.

Avoid `null=True` on string fields. Prefer `blank=True` and an empty string for optional text.

Exception: use `null=True` with `unique=True` and `blank=True` on optional string fields to avoid unique constraint collisions for blank values.

Use `blank=True, null=True` for optional non-string fields such as dates.

Do not use `null=True` just to make forms optional; use `blank=True` for form-level optionality.

## Relations

Use `ForeignKey` for many-to-one relationships.

Use `OneToOneField` for one-to-one relationships.

Use `ManyToManyField` only when the data is genuinely many-to-many.

Use an explicit `through` model when a many-to-many relationship has extra data.

Always set `on_delete` explicitly.

Use clear `related_name` values when reverse access is used or improves readability.

Prefer singular reverse names for one-to-one relations and plural reverse names for collections.

## Choices and Validators

Use `TextChoices` or `IntegerChoices` for stable, closed domains.

Do not add choices prematurely when real data is inconsistent or still evolving.

Use validators on model fields for reusable model-level validation.

Use form `clean_<field>()` methods when accepting user-friendly input such as masks and normalizing before save.

Remember that changing the order of `choices` creates a migration.

## Meta, Constraints, and Indexes

Use `Meta.ordering` only when a default ordering is useful. Ordering has database cost.

Prefer `Meta.indexes` over `db_index` for explicit indexes.

Do not add indexes without a concrete query or access pattern.

Use `UniqueConstraint` and `CheckConstraint` for database-level rules that belong in the schema.

Prefer `UniqueConstraint` over `unique_together`.

Remember that `unique=True` already creates an index.

Define `__str__()` for models that appear in admin, shell, or logs.

## Managers and QuerySets

Use the default `objects` manager unless custom table-level behavior is needed.

Use model methods for row-level behavior.

Use managers or querysets for table-level query behavior.

Prefer `QuerySet.as_manager()` or `Manager.from_queryset()` when custom queryset methods should also be available from the manager.

Be careful with filtered default managers. Django uses the first manager as the default manager.

Do not filter rows out of a base manager, because Django uses base managers to retrieve related objects.

Avoid repository/service layers unless model/query logic becomes non-trivial.

## Migration Rules

Always create migrations when changing models.

Do not edit existing migration files manually.

Review `makemigrations` output before accepting it.

Use `RenameModel` for model renames when preserving existing data.

Use `RunPython` or `RunSQL` only when data conversion or database-specific behavior is necessary.

In data migrations, use historical models through `apps.get_model()`. Do not import current model classes directly.

Commit model changes and their migrations together.

Run `makemigrations --check --dry-run` after model changes.

## Testing Checklist

Test model creation with practical required and optional fields.

Test defaults.

Test `__str__()`.

Test relationships and reverse access names.

Test validators with `full_clean()`.

Test unique constraints and important database constraints.

Test choices for constrained domains.

Test null/blank behavior when it matters.

Test normalization in forms when forms accept masks or user-friendly input.

Run focused app tests after model changes.

Run migration checks after model changes.

## Review Checklist

Does each field type match the real data semantics?

Would a numeric field lose leading zeros or formatting-significant digits?

Are identifiers such as CPF, CEP, and phone stored as validated strings?

Are optional string fields using empty string instead of `NULL`, except for optional unique strings?

Are choices only used for stable closed domains?

Are validators placed at the model level when the rule belongs to the data?

Are form clean methods used when accepting masked input?

Are relationships modeled with the simplest correct Django relation?

Are `related_name` values clear and stable?

Are constraints and indexes justified by real integrity or query needs?

Was a migration created and reviewed?

Were existing migrations left untouched?

Were model tests added or updated?
