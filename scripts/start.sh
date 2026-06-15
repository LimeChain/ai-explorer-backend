#!/bin/sh
set -e

# Run database migrations
uv run --frozen alembic upgrade head

# Start the API server
uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port 8000
