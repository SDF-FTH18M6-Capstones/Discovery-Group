"""Entry point: `flask run` locally, `gunicorn wsgi:app` in production.
With APP_ENV=production the production settings are used (see app/config.py)."""

from app import create_app

app = create_app()