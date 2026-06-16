---
name: django-view
description: Implement or refactor Django views with URLs, templates, forms, tests, and HTMX partials when useful.
---

# Django View

## Use when

The user asks to create or refactor a Django view, endpoint, list view, detail view, create/update view, or HTMX interaction.

## Procedure

1. Inspect the target app structure.
2. Read related views, urls, forms, templates, and tests.
3. Follow the Django, URL, template, testing, and safety conventions in `AGENTS.md`.
4. Choose FBV by default for simple flows.
5. Add or update the URL route.
6. Add or update the template or HTMX partial.
7. Add tests for status code, template usage, permissions, form behavior, and HTMX behavior when relevant.
8. Run the focused test when possible.
9. Show changed files and explain important decisions.

## Rules

- Do not bypass authentication/authorization patterns.
- Create a simple HTML page just for testing the URL when no real template exists yet.
