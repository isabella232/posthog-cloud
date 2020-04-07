release: cd deploy && python manage.py migrate
web: cd deploy && gunicorn posthog.wsgi --log-file -
worker: cd deploy && celery -A posthog worker -b $REDIS_URL