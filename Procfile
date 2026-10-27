release: python manage.py migrate --noinput
web: gunicorn epicoutlet.wsgi --workers ${WEB_CONCURRENCY:-3} --timeout 60 --access-logfile -
