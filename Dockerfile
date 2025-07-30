# Multi-stage build for AI Explorer Backend
# Stage 1: Build dependencies
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables
ENV UV_CACHE_DIR=/tmp/uv-cache

# Set work directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies (generate lock file if needed)
RUN uv sync --no-dev

# Stage 2: Production image
FROM python:3.13-slim AS runtime

# Install uv and curl for runtime and health check
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set work directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY app/ ./app/
COPY pyproject.toml ./


# Setup for MCP servers
COPY mcp_servers/ ./app/mcp_servers
COPY sdk/ ./sdk/

# Running script
COPY scripts/start.sh /app/scripts/start.sh
RUN chmod +x /app/scripts/start.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Run the application
CMD ["/app/scripts/start.sh"]