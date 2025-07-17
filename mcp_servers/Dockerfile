FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy the SDK and MCP server code
COPY ./sdk ./sdk
COPY ./mcp_servers ./mcp_servers

# Install the local SDK as an editable package
RUN cd sdk && uv pip install --system -e .

# Install MCP server dependencies
RUN cd mcp_servers && uv pip install --system -e .

# Expose the MCP server port
EXPOSE 8001

# Run the MCP server
CMD ["python", "mcp_servers/main.py"]