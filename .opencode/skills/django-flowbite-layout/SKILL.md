---
name: django-flowbite-layout
description: Use when building or refactoring Django templates, base layouts, includes, Tailwind CSS, Flowbite components, or Flowbite MCP-driven UI in this project.
compatibility: opencode
metadata:
  project: mdc
  stack: django-tailwind-flowbite
---

# Django Flowbite Layout

Use this skill to create or refactor Django server-rendered layouts with Tailwind CSS, Flowbite, and Flowbite MCP. Follow `AGENTS.md` for project-wide rules and keep this file focused on UI implementation details.

## What This Skill Does

- Sets up a local npm build pipeline for Tailwind CSS and Flowbite.
- Uses Flowbite MCP as the preferred source for component structure, examples, themes, and Figma-to-code workflows.
- Creates maintainable Django template layouts using includes such as `_base.html`, `_header.html`, `_sidebar.html`, `_footer.html`, and `_messages.html`.
- Adapts Flowbite HTML into Django templates using `{% load static %}`, `{% include %}`, `{% block %}`, `{% url %}`, and standard template conditionals.
- Keeps the frontend server-rendered and avoids SPA patterns.

## When To Use

Use this skill when the user asks for any of these tasks:

- Add Tailwind CSS or Flowbite to the Django service.
- Configure Flowbite with a local npm build.
- Create or refactor `base.html`, `_base.html`, `_header.html`, `_sidebar.html`, `_footer.html`, or `_messages.html`.
- Build a Django dashboard, member management layout, auth layout, or reusable template includes.
- Use Flowbite MCP to generate or adapt UI components for Django templates.
- Convert Figma selections into Django templates using Flowbite MCP.

Do not use this skill for unrelated backend-only Django work.

## Project Context

The repository is a monorepo. The Django service lives in `web/`.

Important paths:

```text
web/
├── apps/
├── config/
├── static/
│   ├── css/
│   └── src/
├── templates/
│   ├── base/
│   ├── includes/
│   ├── layouts/
│   ├── account/
│   ├── base.html
│   └── home.html
├── manage.py
├── pyproject.toml
└── Dockerfile
```

Follow `AGENTS.md` for project-wide architecture, frontend, authentication, and testing rules.

## Flowbite MCP Usage

Flowbite MCP is a design and component context server for AI workflows. It helps generate better Tailwind and Flowbite UI, but it does not replace installing Tailwind CSS and Flowbite in the project.

When Flowbite MCP is available:

- Prefer using Flowbite MCP before inventing component markup manually.
- Use it to retrieve or generate navbar, sidebar, footer, alert, form, modal, drawer, table, pagination, card, badge, dropdown, toast, and theme examples.
- Adapt generated HTML into Django templates instead of pasting it blindly.
- Preserve Django template tags and context variables.
- Keep generated components accessible, responsive, and server-rendered.
- Avoid React, Vue, Svelte, or SPA output unless the user explicitly asks for it.

For Figma-to-code:

- Use Flowbite MCP only when the user provides a Figma node link or explicitly asks for Figma conversion.
- `FIGMA_ACCESS_TOKEN` is optional and should only be configured outside the repository through environment variables or user/global opencode config.
- Never commit real Figma tokens or secrets.

This project configures Flowbite MCP in the root `opencode.json`. If Figma conversion is needed, configure the token outside committed project files:

```json
{
  "mcp": {
    "flowbite": {
      "type": "local",
      "command": ["npx", "-y", "flowbite-mcp"],
      "enabled": true,
      "env": {
        "FIGMA_ACCESS_TOKEN": "${FIGMA_ACCESS_TOKEN}"
      }
    }
  }
}
```

After changing opencode MCP config, tell the user to restart opencode because config is loaded at startup.

## Local Build Pipeline

Use a local npm build for Tailwind CSS and Flowbite. Do not use CDN as the default approach for this project.

Preferred location for frontend build files:

```text
web/
├── package.json
├── tailwind.config.js
├── static/
│   ├── css/
│   │   └── app.css
│   └── src/
│       └── input.css
```

Install packages from inside `web/`:

```bash
npm install --save-dev tailwindcss @tailwindcss/cli
npm install flowbite
```

Use `web/static/src/input.css` as the Tailwind source file:

```css
@import "tailwindcss";
@plugin "flowbite/plugin";
@source "../../templates/**/*.html";
@source "../../apps/**/templates/**/*.html";
@source "../../node_modules/flowbite/**/*.js";
```

Use `package.json` scripts similar to this:

```json
{
  "scripts": {
    "build:css": "tailwindcss -i ./static/src/input.css -o ./static/css/app.css --minify",
    "watch:css": "tailwindcss -i ./static/src/input.css -o ./static/css/app.css --watch"
  },
  "dependencies": {
    "flowbite": "latest"
  },
  "devDependencies": {
    "@tailwindcss/cli": "latest",
    "tailwindcss": "latest"
  }
}
```

If the project uses Tailwind CSS v3 instead of v4, adapt to `tailwind.config.js` with `content` and `plugins: [require("flowbite/plugin")]`. Do not mix v3 and v4 configuration styles.

Ensure Django can find project-level static files. Add `STATICFILES_DIRS` in `web/config/settings.py` when needed:

```python
STATICFILES_DIRS = [BASE_DIR / "static"]
```

Include the compiled stylesheet and Flowbite JavaScript from Django templates:

```django
{% load static %}
<link rel="stylesheet" href="{% static 'css/app.css' %}">
<script src="{% static 'node_modules/flowbite/dist/flowbite.min.js' %}" defer></script>
```

If serving `node_modules` directly through Django static files is not desired, copy or bundle Flowbite JavaScript into `web/static/js/flowbite.min.js` during the build and reference that file instead.

## Template Organization

Prefer this layout structure:

```text
web/templates/
├── base.html
├── layouts/
│   └── _base.html
├── includes/
│   ├── _footer.html
│   ├── _header.html
│   ├── _messages.html
│   └── _sidebar.html
├── account/
└── home.html
```

Keep `base.html` as the public inheritance entry point for existing templates. It may extend or include `layouts/_base.html`, or it may be replaced with the layout content if that is simpler.

Prefer these blocks:

```django
{% block title %}{% endblock %}
{% block body_class %}{% endblock %}
{% block header %}{% endblock %}
{% block sidebar %}{% endblock %}
{% block content %}{% endblock %}
{% block footer %}{% endblock %}
{% block extra_js %}{% endblock %}
```

Do not add too many blocks before they are needed.

## Example Base Layout

Use Flowbite MCP to improve or replace this structure when possible, then adapt it to Django.

`web/templates/base.html`:

```django
{% extends "layouts/_base.html" %}
```

`web/templates/layouts/_base.html`:

```django
{% load static %}
<!DOCTYPE html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Gestão de Membros{% endblock %}</title>
    <link rel="stylesheet" href="{% static 'css/app.css' %}">
  </head>
  <body class="bg-gray-50 text-gray-900 antialiased {% block body_class %}{% endblock %}">
    {% block header %}
      {% include "includes/_header.html" %}
    {% endblock %}

    <div class="min-h-screen pt-16">
      {% block sidebar %}
        {% if request.user.is_authenticated %}
          {% include "includes/_sidebar.html" %}
        {% endif %}
      {% endblock %}

      <main class="p-4 {% if request.user.is_authenticated %}sm:ml-64{% endif %}">
        <div class="mx-auto max-w-7xl">
          {% include "includes/_messages.html" %}
          {% block content %}{% endblock %}
        </div>
      </main>
    </div>

    {% block footer %}
      {% include "includes/_footer.html" %}
    {% endblock %}

    <script src="{% static 'js/flowbite.min.js' %}" defer></script>
    {% block extra_js %}{% endblock %}
  </body>
</html>
```

## Example Header Include

`web/templates/includes/_header.html`:

```django
<nav class="fixed left-0 right-0 top-0 z-50 border-b border-gray-200 bg-white">
  <div class="flex h-16 items-center justify-between px-4">
    <div class="flex items-center gap-3">
      {% if request.user.is_authenticated %}
        <button type="button" class="inline-flex items-center rounded-lg p-2 text-sm text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-200 sm:hidden" data-drawer-target="app-sidebar" data-drawer-toggle="app-sidebar" aria-controls="app-sidebar">
          <span class="sr-only">Abrir menu</span>
          <svg class="h-6 w-6" aria-hidden="true" fill="currentColor" viewBox="0 0 20 20"><path clip-rule="evenodd" fill-rule="evenodd" d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75Zm0 5A.75.75 0 0 1 2.75 9h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 9.75Zm0 5A.75.75 0 0 1 2.75 14h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 14.75Z"></path></svg>
        </button>
      {% endif %}
      <a href="{% url 'home' %}" class="text-lg font-semibold text-gray-900">MDC</a>
    </div>

    <div class="flex items-center gap-3">
      {% if request.user.is_authenticated %}
        <span class="hidden text-sm text-gray-600 sm:inline">{{ request.user.email|default:request.user.username }}</span>
        <a href="{% url 'account_logout' %}" class="rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100">Sair</a>
      {% else %}
        <a href="{% url 'account_login' %}" class="rounded-lg bg-blue-700 px-3 py-2 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300">Entrar</a>
      {% endif %}
    </div>
  </div>
</nav>
```

## Example Sidebar Include

`web/templates/includes/_sidebar.html`:

```django
<aside id="app-sidebar" class="fixed left-0 top-0 z-40 h-screen w-64 -translate-x-full border-r border-gray-200 bg-white pt-16 transition-transform sm:translate-x-0" aria-label="Menu lateral">
  <div class="h-full overflow-y-auto px-3 py-4">
    <ul class="space-y-2 font-medium">
      <li>
        <a href="{% url 'home' %}" class="flex items-center rounded-lg p-2 text-gray-900 hover:bg-gray-100">
          <span>Início</span>
        </a>
      </li>
      <li>
        <a href="#" class="flex items-center rounded-lg p-2 text-gray-900 hover:bg-gray-100">
          <span>Membros</span>
        </a>
      </li>
    </ul>
  </div>
</aside>
```

Replace placeholder URLs when app routes exist. Prefer namespaced URLs such as `{% url 'members:list' %}`.

## Example Messages Include

`web/templates/includes/_messages.html`:

```django
{% if messages %}
  <div class="mb-6 space-y-3">
    {% for message in messages %}
      <div class="rounded-lg border p-4 text-sm {% if message.tags == 'error' %}border-red-200 bg-red-50 text-red-800{% elif message.tags == 'success' %}border-green-200 bg-green-50 text-green-800{% else %}border-blue-200 bg-blue-50 text-blue-800{% endif %}" role="alert">
        {{ message }}
      </div>
    {% endfor %}
  </div>
{% endif %}
```

## Example Footer Include

`web/templates/includes/_footer.html`:

```django
<footer class="border-t border-gray-200 bg-white p-4 {% if request.user.is_authenticated %}sm:ml-64{% endif %}">
  <div class="mx-auto flex max-w-7xl flex-col gap-2 text-sm text-gray-500 sm:flex-row sm:items-center sm:justify-between">
    <span>&copy; {% now "Y" %} MDC. Todos os direitos reservados.</span>
    <span>Gestão de membros da igreja</span>
  </div>
</footer>
```

## Forms And Auth Templates

When styling Django forms:

- Prefer explicit field rendering over `form.as_p` for important user-facing forms.
- Keep `form.as_p` only for quick internal placeholders.
- Use Flowbite form classes for inputs, labels, help text, and errors.
- Preserve CSRF tokens and allauth field names.
- Do not rewrite allauth behavior manually.

Example field pattern:

```django
<div>
  <label for="{{ form.email.id_for_label }}" class="mb-2 block text-sm font-medium text-gray-900">E-mail</label>
  {{ form.email }}
  {% if form.email.errors %}
    <p class="mt-2 text-sm text-red-600">{{ form.email.errors|striptags }}</p>
  {% endif %}
</div>
```

If custom widget classes are needed, prefer adding them in Django forms where appropriate instead of complex template filters.

## HTMX Guidance

Use HTMX only where it improves the server-rendered UX, such as:

- Member search results.
- Inline delete confirmation.
- Partial form validation.
- Toast or alert updates.

When combining HTMX with Flowbite:

- Return partial templates for HTMX requests.
- Reinitialize Flowbite interactive components after swaps when needed.
- Keep fallback full-page behavior for non-HTMX requests.
- Keep JavaScript local to the interaction being enhanced.

## Verification

After implementing layout or build changes:

- Run the CSS build command from `web/`.
- Run Django tests from `web/` if tests exist.
- Run `python manage.py collectstatic --noinput` when static file configuration changes.
- Manually check desktop and mobile layout behavior, especially sidebar drawer and navbar dropdowns.
- Confirm templates still render for authenticated and anonymous users.

Preferred commands:

```bash
npm run build:css
uv run pytest
uv run python manage.py collectstatic --noinput
```

## Implementation Rules

- Use Flowbite MCP for component guidance when available, but always adapt output to this Django project.
- Keep `base.html` compatibility unless the user explicitly approves a broader migration.
- Do not use CDN assets as the primary implementation.
- Do not commit secrets, Figma tokens, or generated credentials.
- Do not add UI routes or backend architecture that the user did not ask for.
- Prefer a clean, practical church management layout over generic dashboard clutter.
