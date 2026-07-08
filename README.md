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

3. Optionally create an admin user:

   ```bash
   docker compose exec web uv run python manage.py createsuperuser
   ```

4. Open the application:

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

## Container startup

The Docker images use `web/entrypoint.sh` before the configured container
command. By default, the entrypoint does not run database migrations.

Migrations run only when `DJANGO_RUN_MIGRATIONS` is explicitly set to `true`:

```sh
if [ "${DJANGO_RUN_MIGRATIONS:-false}" = "true" ]; then
  python manage.py migrate --noinput
fi
```

The local `compose.yaml` sets `DJANGO_RUN_MIGRATIONS: "true"` for the `web`
service, so local containers apply pending migrations before starting Django's
development server. In production, configure `DJANGO_RUN_MIGRATIONS=true` only
on the application service responsible for running migrations. Do not set it on
future worker, queue, or maintenance services unless they are intentionally
responsible for migrations.

After the optional migration step, the entrypoint delegates to the container
command with `exec "$@"`. The production image keeps Gunicorn as the default
`CMD`.

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

## Member photos and media storage

Local development uses Django filesystem media storage by default. Uploaded
member photos are stored under `web/mediafiles/` and served by Django only when
`DJANGO_DEBUG=1`.

To use a RustFS/S3-compatible service with private member photos, keep RustFS as
a separate service and enable S3 explicitly. Uploaded files stay private in the
bucket, and `django-storages` generates short-lived presigned URLs when Django
renders `member.photo.url` in authenticated pages.

```env
DJANGO_USE_S3=1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=mdc-media
AWS_S3_ENDPOINT_URL=https://s3.faramir.com.br
AWS_S3_REGION_NAME=us-east-1
AWS_S3_ADDRESSING_STYLE=path
AWS_S3_SIGNATURE_VERSION=s3v4
AWS_QUERYSTRING_AUTH=1
AWS_QUERYSTRING_EXPIRE=300
AWS_DEFAULT_ACL=private
```

The bucket named in `AWS_STORAGE_BUCKET_NAME` must exist before the first upload.
The example bucket name is `mdc-media`; change it through the environment for
each deployment. Uploaded media is stored with the `media/` prefix inside the
bucket.

For presigned URLs, `AWS_S3_ENDPOINT_URL` must be reachable both by the Django
container and by users' browsers. Do not set it to an internal-only Docker host
such as `http://rustfs:9000` for this mode, because the generated URL would also
contain that internal hostname. In Dokploy, point it to the public HTTPS RustFS
endpoint, for example `https://s3.faramir.com.br`.

Keep `AWS_S3_CUSTOM_DOMAIN` empty when `AWS_QUERYSTRING_AUTH=1`. The S3 backend
generates presigned URLs from `AWS_S3_ENDPOINT_URL`; setting a custom domain is
only useful for public, unsigned media URLs or a separate CDN signing setup.

If the RustFS deployment does not accept object ACLs, use an empty ACL and rely
on the bucket policy/user permissions instead:

```env
AWS_DEFAULT_ACL=
```

Do not add public bucket policies for member photos. The Django access key needs
read/write permissions for `mdc-media/media/*`, while browser access should
happen through presigned URLs that expire after `AWS_QUERYSTRING_EXPIRE` seconds.
`AWS_S3_SIGNATURE_VERSION=s3v4` keeps signing explicit for RustFS-compatible
presigned URLs.

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

Production database migrations are not moved to GitHub Actions; they are handled
by the container startup flow when `DJANGO_RUN_MIGRATIONS=true` is configured
for the application service.
