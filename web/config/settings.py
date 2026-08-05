"""Django settings for the web service."""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import sentry_sdk
from botocore.config import Config


BASE_DIR = Path(__file__).resolve().parent.parent


def parse_csv_env(name, default=""):
    """Return comma-separated environment variable values as a clean list."""
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]


def parse_bool_env(name, default=False):
    """Return whether an environment variable contains a truthy value."""
    return os.environ.get(name, str(int(default))).lower() in {"1", "true", "yes", "on"}


def parse_int_env(name, default):
    """Return an integer environment variable value or the provided default."""
    value = os.environ.get(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def database_config_from_url(database_url):
    """Return Django database settings parsed from a PostgreSQL DATABASE_URL."""
    parsed_url = urlparse(database_url)

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed_url.path.lstrip("/")),
        "USER": unquote(parsed_url.username or ""),
        "PASSWORD": unquote(parsed_url.password or ""),
        "HOST": parsed_url.hostname or "",
        "PORT": str(parsed_url.port or 5432),
    }

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "change-me")

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

ALLOWED_HOSTS = parse_csv_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

CSRF_TRUSTED_ORIGINS = parse_csv_env("DJANGO_CSRF_TRUSTED_ORIGINS")

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        send_default_pii=parse_bool_env("SENTRY_SEND_DEFAULT_PII"),
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "django_cotton",
    "storages",
    "apps.birthdays",
    "apps.members",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASES = {
    "default": database_config_from_url(DATABASE_URL)
    if DATABASE_URL
    else {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DATABASE_NAME", "mdc"),
        "USER": os.environ.get("DATABASE_USER", "mdc"),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD", "mdc"),
        "HOST": os.environ.get("DATABASE_HOST", "db"),
        "PORT": os.environ.get("DATABASE_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"
MEDIA_LOCATION = "media"

STATICFILES_STORAGE_BACKEND = os.environ.get(
    "DJANGO_STATICFILES_STORAGE",
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage",
)

def media_storage_config():
    """Return the default file storage configuration for local or S3 media."""
    if not parse_bool_env("DJANGO_USE_S3"):
        return {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        }

    querystring_auth = parse_bool_env("AWS_QUERYSTRING_AUTH", default=True)
    default_acl = os.environ.get("AWS_DEFAULT_ACL", "private") or None
    addressing_style = os.environ.get("AWS_S3_ADDRESSING_STYLE", "path")
    signature_version = os.environ.get("AWS_S3_SIGNATURE_VERSION", "s3v4")
    options = {
        "access_key": os.environ.get("AWS_ACCESS_KEY_ID", ""),
        "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        "bucket_name": os.environ.get("AWS_STORAGE_BUCKET_NAME", ""),
        "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL", ""),
        "region_name": os.environ.get("AWS_S3_REGION_NAME", "us-east-1"),
        "addressing_style": addressing_style,
        "signature_version": signature_version,
        "querystring_auth": querystring_auth,
        "querystring_expire": parse_int_env("AWS_QUERYSTRING_EXPIRE", 300),
        "default_acl": default_acl,
        "location": MEDIA_LOCATION,
        "client_config": Config(
            connect_timeout=parse_int_env("AWS_S3_CONNECT_TIMEOUT", 5),
            read_timeout=parse_int_env("AWS_S3_READ_TIMEOUT", 15),
            retries={
                "max_attempts": parse_int_env("AWS_S3_MAX_ATTEMPTS", 2),
                "mode": os.environ.get("AWS_S3_RETRY_MODE", "standard"),
            },
            s3={"addressing_style": addressing_style},
            signature_version=signature_version,
        ),
    }

    custom_domain = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")
    if custom_domain and not querystring_auth:
        options["custom_domain"] = custom_domain
        options["url_protocol"] = os.environ.get("AWS_S3_URL_PROTOCOL", "https:")

    return {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": options,
    }


STORAGES = {
    "default": media_storage_config(),
    "staticfiles": {
        "BACKEND": STATICFILES_STORAGE_BACKEND,
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = parse_bool_env("EMAIL_USE_TLS")
EMAIL_USE_SSL = parse_bool_env("EMAIL_USE_SSL")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "webmaster@localhost")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_UNIQUE_EMAIL = True
