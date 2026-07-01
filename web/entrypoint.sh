#!/bin/sh
set -e

if [ "${DJANGO_RUN_MIGRATIONS:-false}" = "true" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
