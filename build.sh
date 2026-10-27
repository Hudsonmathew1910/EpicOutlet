#!/usr/bin/env bash
# Render build step: install, collect static files, apply migrations.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
