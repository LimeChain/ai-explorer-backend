#!/bin/sh
set -e

# Run database migrations
uv run alembic upgrade head

# Start the API server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000