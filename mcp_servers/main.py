#!/usr/bin/env python3
"""Entry point for the MCP server."""

from app.main import mcp

if __name__ == "__main__":
    mcp.settings.port = 8001
    mcp.settings.host = "0.0.0.0"  # Bind to all interfaces for Docker
    mcp.run(transport="streamable-http")