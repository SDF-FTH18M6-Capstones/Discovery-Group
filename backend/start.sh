#!/usr/bin/env bash
set -euo pipefail

flask --app wsgi db upgrade

if [ "${SEED_DEMO:-false}" = "true" ]; then
  python seed.py
fi

exec gunicorn wsgi:app --workers 2 --threads 4 --bind "0.0.0.0:${PORT:-5000}" --access-logfile -
