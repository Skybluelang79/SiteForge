#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-1}" != "0" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
fi

if [ "$SEED_DEMO_DATA" = "1" ]; then
  python manage.py seed_dev_data --reset
fi

if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput --email "$DJANGO_SUPERUSER_EMAIL" || true
fi

exec "$@"
