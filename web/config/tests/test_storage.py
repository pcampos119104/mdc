"""Tests for media storage settings."""

from config.settings import media_storage_config


def test_media_storage_uses_local_filesystem_by_default(monkeypatch):
    """Local filesystem storage should be used unless S3 is explicitly enabled."""
    monkeypatch.delenv("DJANGO_USE_S3", raising=False)

    storage_config = media_storage_config()

    assert storage_config == {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }


def test_media_storage_uses_s3_when_enabled(monkeypatch):
    """S3 storage should generate private RustFS presigned URLs."""
    monkeypatch.setenv("DJANGO_USE_S3", "1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "example-access-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "example-secret-key")
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "mdc-media")
    monkeypatch.setenv("AWS_S3_ENDPOINT_URL", "https://s3.faramir.com.br")
    monkeypatch.setenv("AWS_S3_REGION_NAME", "us-east-1")
    monkeypatch.setenv("AWS_S3_ADDRESSING_STYLE", "path")
    monkeypatch.setenv("AWS_S3_SIGNATURE_VERSION", "s3v4")
    monkeypatch.setenv("AWS_QUERYSTRING_AUTH", "1")
    monkeypatch.setenv("AWS_QUERYSTRING_EXPIRE", "300")
    monkeypatch.setenv("AWS_DEFAULT_ACL", "private")
    monkeypatch.setenv("AWS_S3_CUSTOM_DOMAIN", "media.example.com")
    monkeypatch.setenv("AWS_S3_CONNECT_TIMEOUT", "4")
    monkeypatch.setenv("AWS_S3_READ_TIMEOUT", "12")
    monkeypatch.setenv("AWS_S3_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("AWS_S3_RETRY_MODE", "standard")

    storage_config = media_storage_config()
    storage_options = dict(storage_config["OPTIONS"])
    client_config = storage_options.pop("client_config")

    assert storage_config["BACKEND"] == "storages.backends.s3.S3Storage"
    assert storage_options == {
        "access_key": "example-access-key",
        "secret_key": "example-secret-key",
        "bucket_name": "mdc-media",
        "endpoint_url": "https://s3.faramir.com.br",
        "region_name": "us-east-1",
        "addressing_style": "path",
        "signature_version": "s3v4",
        "querystring_auth": True,
        "querystring_expire": 300,
        "default_acl": "private",
        "location": "media",
    }
    assert client_config.connect_timeout == 4
    assert client_config.read_timeout == 12
    assert client_config.retries == {"max_attempts": 2, "mode": "standard"}
    assert client_config.s3 == {"addressing_style": "path"}
    assert client_config.signature_version == "s3v4"


def test_media_storage_allows_unsigned_custom_domain(monkeypatch):
    """Custom domains are only applied for unsigned public media URLs."""
    monkeypatch.setenv("DJANGO_USE_S3", "1")
    monkeypatch.setenv("AWS_QUERYSTRING_AUTH", "0")
    monkeypatch.setenv("AWS_S3_CUSTOM_DOMAIN", "media.example.com")

    storage_config = media_storage_config()

    assert storage_config["OPTIONS"]["querystring_auth"] is False
    assert storage_config["OPTIONS"]["custom_domain"] == "media.example.com"
