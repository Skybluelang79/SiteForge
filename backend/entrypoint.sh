#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "$SEED_DEMO_DATA" = "1" ]; then
  python manage.py seed_dev_data --reset
elif [ "$RENDER" = "true" ]; then
  python manage.py seed_dev_data
fi

if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput --email "$DJANGO_SUPERUSER_EMAIL" || true
fi

exec "$@"
