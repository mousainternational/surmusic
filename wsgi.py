"""WSGI entry point: `gunicorn wsgi:app` (production) or `flask --app wsgi run` (development)."""
from app import create_app

app = create_app()
