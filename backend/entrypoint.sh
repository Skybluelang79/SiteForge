#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "$SEED_DEMO_DATA" = "1" ]; then
  python manage.py seed_dev_data --reset
fi

exec "$@"
