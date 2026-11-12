"""Entry point: `flask run` locally, `gunicorn wsgi:app` in production."""

from app import create_app

app = create_app()