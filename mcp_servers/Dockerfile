# Multi-stage build for MCP Server
# Stage 1: Build dependencies
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables
ENV UV_CACHE_DIR=/tmp/uv-cache

# Set work directory
WORKDIR /app

# Copy workspace configuration and dependency files
COPY pyproject.toml uv.lock ./
COPY sdk/ ./sdk/
COPY mcp_servers/ ./mcp_servers/

# Install dependencies
RUN uv sync --frozen
# Install SDK in editable mode (explicit dependency)
RUN uv pip install -e ./sdk --no-deps

# Stage 2: Production image
FROM python:3.13-slim AS runtime

# Install uv for runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set work directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code and workspace config
COPY pyproject.toml ./
COPY mcp_servers/ ./mcp_servers/
COPY sdk/ ./sdk/

# Expose the MCP server port
EXPOSE 8001

# Run the MCP server
CMD ["uv", "run", "python", "mcp_servers/main.py"]