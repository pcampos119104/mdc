# AGENTS.md

## Project Overview

This is a church member management system.

The goal is to help the church keep an organized record of its members so leadership can better follow, support, and guide them.

The system is structured as a monorepo. Currently, it contains only one service, but more services may be added in the future. Keep the monorepo structure even while the project has a single service.

## Current Services

### `web/`

The main web application.

Stack:

- Python
- Django
- django-allauth
- PostgreSQL
- HTMX
- Tailwind CSS
- Docker
- uv

Initial features:

- Login/logout
- Password reset
- Member CRUD
- Member list with search
- Deployment with Docker, GitHub Actions, and Dokploy

## General Development Principles

- Prefer simple and idiomatic Django solutions.
- Avoid premature abstractions.
- Avoid adding dependencies unless there is a clear and practical need.
- Prefer Django built-in features before adding third-party packages.
- Keep the code readable, explicit, and easy to maintain.
- Do not create APIs, queues, microservices, repository/service layers, or complex architecture unless explicitly requested.
- Make small and coherent changes.
- Do not rewrite unrelated parts of the project.
- Preserve the existing project structure and conventions.

## Monorepo Guidelines

- Keep each service isolated in its own directory.
- The current Django service lives in `web/`.
- Shared files such as `README.md`, root `compose.yaml`, CI/CD files, and global documentation may live at the repository root.
- Service-specific documentation should live inside the service directory.
- Do not move service-specific code to the repository root.
- Future services should be added as sibling directories to `web/`.

Example structure:

    .
    ├── web/
    │   ├── config/
    │   ├── apps/
    │   ├── manage.py
    │   ├── pyproject.toml
    │   └── Dockerfile
    ├── docker/
    ├── .github/
    │   └── workflows/
    ├── compose.yaml
    ├── README.md
    └── AGENTS.md

## Django App Structure

Inside the `web/` service, Django apps should live under `apps/`.

Expected initial apps:

    web/
    ├── apps/
    │   ├── accounts/
    │   └── members/

Use:

- `apps/accounts` for authentication-related code, only if custom authentication behavior is needed.
- `apps/members` for member registration and management.
- `/` for settings, root URLs, WSGI, ASGI, and etc.

## Django View Guidelines

When creating views:

- Prefer function-based views for simple endpoints.
- If a view needs both `GET` and `POST`, use `django.views.View` with explicit `get()` and `post()` methods.
- Use class-based views only when they clearly reduce complexity.
- Do not use generic class-based views unless explicitly requested.
- Always add docstrings to views, methods, and helper functions.
- Keep views small and focused.
- Use forms for validation when appropriate.
- Do not put complex business logic directly inside templates.
- Use services/selectors only when logic becomes non-trivial.

Example:

    from django.shortcuts import render
    from django.views import View


    def member_list(request):
        """Display the list of members, optionally filtered by search query."""
        ...


    class MemberCreateView(View):
        """Create a new church member."""

        def get(self, request):
            """Display the member creation form."""
            ...

        def post(self, request):
            """Validate and create a new member."""
            ...

## URL Guidelines

When adding routes:

- Add app-specific URLs in the app's `urls.py`.
- Include the app's `urls.py` in the project-level `config/urls.py`.
- Use clear and stable route names.
- Prefer namespaced URLs for apps.

Example:

    # apps/members/urls.py

    from django.urls import path

    from . import views

    app_name = "members"

    urlpatterns = [
        path("", views.member_list, name="list"),
        path("new/", views.MemberCreateView.as_view(), name="create"),
    ]

    # config/urls.py

    from django.urls import include, path

    urlpatterns = [
        path("members/", include("apps.members.urls")),
    ]

## Testing Guidelines

Always create tests for every created view.

Use:

- `pytest`
- `pytest-django`

Prefer focused tests before running the full suite. When implementing a small feature, run a single relevant test before running all tests.

Tests should live inside a `tests/` directory within the related app.

Example:

    apps/
    └── members/
        ├── tests/
        │   ├── __init__.py
        │   ├── test_views.py
        │   └── test_forms.py
        ├── views.py
        ├── urls.py
        └── forms.py

For each view, test at least:

- The expected status code.
- The template used, when applicable.
- Access control, when applicable.
- Successful form submission, when applicable.
- Invalid form submission, when applicable.

## Templates and Frontend

- Use Django templates, Tailwind CSS, Flowbite, HTMX and Alpine.js when useful.
- Keep templates simple and server-rendered.
- Prefer reusable partials under `templates/includes/` or app-level `templates/<app>/partials/`.
- Do not put business logic in templates.
- Use Flowbite components for layout, forms, cards, tables, alerts and navigation.
- When unsure about Flowbite component usage, use the Flowbite MCP.
- Use HTMX only where it clearly improves UX.
- Avoid building a SPA.
- Keep Alpine.js usage minimal and local to the template behavior.
- Keep templates organized under template directory follow by app folder name.

Example:

 web/
 └── templates/
     └── members/
         ├── partials/
         │   └── _member_table.html
         ├── member_list.html
         ├── member_form.html
         └── member_confirm_delete.html

## Database and Models

- Use PostgreSQL as the main database.
- Keep models simple and explicit.
- Do not add fields before they are needed.
- Always create migration when changing models
- Never edit existing migration files manually.
- Use clear verbose names when they improve admin/readability.

### Model Creation Guidelines

When creating Django models for this project:

- Derive fields from real source material provided by the user, such as spreadsheets, PDFs, exported forms, and existing records.
- Prefer simple and explicit first-version models.
- Create multiple models only when the data clearly indicates separate relationships.
- If a separate structure does not add clear value yet, prefer integrating the fields into the main model.
- Use English names for model classes and fields.
- Always add docstrings to models in English.
- Add `help_text` to model fields in Portuguese when the fields are user-facing or likely to appear in forms/admin.
- Add `is_active` when an internal active/inactive status is useful for the system.
- Avoid premature `choices` when the real data still shows inconsistent or evolving categories.
- Remove or avoid ambiguous fields if the user indicates they should not be part of the first version.
- Add tests for created models, including practical coverage for defaults, relationships, and important metadata when appropriate.

## Authentication

Use `django-allauth` as the authentication package.

Authentication should support:

- Login
- Logout
- Password reset
- Password change, when applicable

Use Django's built-in user model unless a custom user model is explicitly required before the first migration.

Do not implement custom authentication flows manually when `django-allauth` already provides the required behavior.

Keep authentication templates simple and consistent with the rest of the Django template structure.

Protect member management views behind authentication.

## Deployment

The project should be deployable with:

- Docker
- GitHub Actions
- Dokploy

Deployment-related files should be kept simple and explicit.

Do not introduce Kubernetes, Terraform, Ansible, or complex infrastructure tooling unless explicitly requested.

## Safety

- Never modify `.env` or production configuration without approval.

## Workflow

Before making broad changes:

1. Briefly explain the plan.
2. Make small, coherent changes.
3. Run tests when available.
4. Update documentation when it makes sense.

When modifying existing code:

- Respect the current structure.
- Avoid unrelated refactors.
- Keep changes focused on the requested task.
- Prefer incremental improvements.

## Initial Priorities

1. Create the monorepo structure.
2. Set up the Django service in `web/`.
3. Configure local development with Docker.
4. Configure PostgreSQL.
5. Implement authentication.
6. Implement member CRUD.
7. Implement member search.
8. Add tests.
9. Prepare CI/CD.
10. Prepare Dokploy deployment.

## Important Constraints

Keep this project simple.

This is not an enterprise SaaS platform at this stage. It is a focused church member management system.

Do not overengineer.
