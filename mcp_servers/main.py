#!/usr/bin/env python3
"""Entry point for the MCP server."""
from app.main import mcp
from app.logging_config import setup_logging, get_logger

# Setup logging for the main entry point
setup_logging(level="INFO", use_json=False, service_name="mcp")
logger = get_logger(__name__, service_name="mcp")

if __name__ == "__main__":
    try:
        logger.info("🚀 Starting MCP server")
        mcp.settings.port = 8001
        mcp.settings.host = "0.0.0.0"  # Bind to all interfaces for Docker
        logger.info(f"⚙️ Server configured to run on {mcp.settings.host}:{mcp.settings.port}")
        mcp.run(transport="streamable-http")
    except Exception as e:
        logger.error("❌ Failed to start MCP server", exc_info=True)
        raise