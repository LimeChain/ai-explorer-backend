#!/usr/bin/env python3
"""Entry point for the MCP server."""

import sys
import os
# Add the mcp_servers directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import mcp

if __name__ == "__main__":
    mcp.settings.port = 8001
    mcp.run(transport="streamable-http")