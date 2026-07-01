# Church Member Management

Initial monorepo structure for a church member management system.

## Services

- `web/`: Django web application

## Requirements

- Docker
- Docker Compose

## Local development

1. Copy the environment file:

   ```bash
   cp .env.example .env
   ```

2. Build and start the containers:

   ```bash
   docker compose up --build
   ```

3. In another terminal, run the database migrations:

   ```bash
   docker compose exec web uv run python manage.py migrate
   ```

4. Optionally create an admin user:

   ```bash
   docker compose exec web uv run python manage.py createsuperuser
   ```

5. Open the application:

   - Home page: http://localhost:8000/
   - Admin: http://localhost:8000/admin/
   - Accounts: http://localhost:8000/accounts/login/

## Useful commands

Build the local development stack:

```bash
just build
```

Run database migrations:

```bash
just mng migrate
```

Run Django checks:

```bash
docker compose exec web uv run python manage.py check
```

Run tests:

```bash
just test
```

Build the production image locally:

```bash
just prod-build
```

## Production email

The app reads email settings from environment variables. Local development uses
the console email backend by default.

For Resend SMTP in production, configure:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.resend.com
EMAIL_PORT=587
EMAIL_HOST_USER=resend
EMAIL_HOST_PASSWORD=re_your_resend_api_key
EMAIL_USE_TLS=1
EMAIL_USE_SSL=0
DEFAULT_FROM_EMAIL=MDC <noreply@your-domain.com>
SERVER_EMAIL=MDC <noreply@your-domain.com>
```

The sender domain must be verified in Resend before production emails can be
delivered.

## Sentry

The app can report errors to Sentry when `SENTRY_DSN` is configured. Leave
`SENTRY_DSN` empty to disable Sentry, which is the default for local
development.

Create a Django project in Sentry, copy the DSN, and configure these environment
variables in `.env` for local usage or in Dokploy for production:

```env
SENTRY_DSN=https://examplePublicKey@o0.ingest.sentry.io/0
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_SEND_DEFAULT_PII=0
```

`SENTRY_TRACES_SAMPLE_RATE` controls performance tracing. Use `0.0` to disable
tracing or a small value such as `0.1` in production to sample 10% of requests.
Keep `SENTRY_SEND_DEFAULT_PII=0` unless sending user-identifying data to Sentry
is intentional and approved.

To test the integration locally, configure `SENTRY_DSN` and start the app with
`DJANGO_DEBUG=1`. Then open:

```text
http://localhost:8000/sentry-debug/
```

This route intentionally raises an error and only exists when `DEBUG` is enabled.
The error should appear in the configured Sentry project.

## CI/CD

GitHub Actions runs the test suite on pull requests and pushes to `main` using `.github/workflows/ci.yml`.

When CI succeeds for a push to `main`, `.github/workflows/push-image.yml` builds `web/Dockerfile` and publishes the image to GitHub Container Registry as `ghcr.io/<owner>/<repo>:latest` and `ghcr.io/<owner>/<repo>:sha-<commit>`.
