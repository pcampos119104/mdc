FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN apt-get update && \
    apt-get install --no-install-recommends -y poppler-utils && \
    rm -rf /var/lib/apt/lists/* && \
    uv sync --frozen --no-dev --no-install-project && \
    playwright install --with-deps chromium

COPY . .
RUN chmod +x /app/entrypoint.sh && \
    uv sync --frozen --no-dev && \
    python manage.py collectstatic --noinput --ignore 'src/*'

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120"]
