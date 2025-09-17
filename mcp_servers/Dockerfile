FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy the SDK, MCP server code, and SDK documentation
COPY ./sdk ./sdk
COPY ./mcp_servers ./mcp_servers
COPY ./hiero_mirror_sdk_methods.json ./hiero_mirror_sdk_methods.json
COPY ./hgraph_graphql_schema.json ./hgraph_graphql_schema.json
COPY ./hgraph_graphql_metadata.json ./hgraph_graphql_metadata.json  


# Install the local SDK as an editable package
RUN cd sdk && uv pip install --system -e .

# Install MCP server dependencies
RUN cd mcp_servers && uv pip install --system -e .

# Expose the MCP server port
EXPOSE 8001

# Run the MCP server
CMD ["python", "mcp_servers/main.py"]