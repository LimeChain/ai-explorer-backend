#!/bin/sh
set -e

# Run migrations
uv run alembic upgrade head

# Start the backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000