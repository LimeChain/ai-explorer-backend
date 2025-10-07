# Hedera AI Agent MCP Server

A Model Context Protocol (MCP) server that exposes Hedera blockchain expertise to external AI agents. This server allows other AI systems to query the Hedera blockchain and receive intelligent, context-aware responses powered by the AI Explorer backend.

## 🎯 Purpose

This MCP server acts as a bridge between external AI agents and the Hedera blockchain, providing:

- **Natural language blockchain queries** - Ask questions in plain English about Hedera transactions, accounts, and network activity
- **Intelligent analysis** - Get AI-powered insights and summaries of blockchain data
- **Multi-network support** - Query mainnet, testnet, or previewnet
- **Contextual responses** - Account-specific insights when account ID is provided

## 🛠️ Installation

### Prerequisites

- Python 3.11+
- Access to a running AI Explorer backend API
- MCP-compatible AI system (Claude Desktop, OpenAI with MCP, etc.)

### Setup

1. **Install dependencies**:
   ```bash
   cd mcp_external
   pip install -e .
   ```

2. **Configure environment** (optional):
   ```bash
   # Create .env file
   echo "API_BASE_URL=ws://localhost:8000" > .env
   echo "LOG_LEVEL=INFO" >> .env
   ```

3. **Test the server**:
   ```bash
   python -m mcp_external.main
   ```

## 🚀 Usage

### Running the Server

The server supports HTTP transport using FastMCP's `streamable-http` protocol:

```bash
# From the project root
python mcp_external/main.py
```

This will start the server on `http://localhost:8002/mcp` (port 8002).

### Connecting with Postman MCP

1. Open Postman
2. Create a new MCP connection
3. Set the URL to: `http://localhost:8002/mcp`
4. The server will automatically discover and expose the available tools

### Available Tools

#### `ask_explorer`

Ask questions about the Hedera blockchain and receive intelligent AI-powered responses.

**Parameters:**
- `question` (required): Your question about Hedera blockchain
- `network` (optional): Network to query - "mainnet", "testnet", or "previewnet" (default: "mainnet")
- `account_id` (optional): Hedera account ID for contextual responses (format: "0.0.123")

**Examples:**

```json
{
  "question": "What are the recent transactions for account 0.0.123?",
  "network": "mainnet"
}
```

```json
{
  "question": "Analyze transaction 0.0.456@1234567890 and explain what happened",
  "network": "mainnet"
}
```

```json
{
  "question": "What is the current network status and recent activity?",
  "network": "mainnet"
}
```

```json
{
  "question": "Show me NFT activity and trading volume today",
  "network": "mainnet",
  "account_id": "0.0.789"
}
```

### Integration with AI Systems

#### Postman MCP (Recommended)

1. Start the server: `python mcp_external/main.py`
2. In Postman, connect to: `http://localhost:8002/mcp`
3. Postman will auto-discover the `ask_explorer` tool
4. Use the tool to query the Hedera blockchain

#### Claude Desktop (stdio)

For stdio-based integration, modify the main.py to use stdio transport instead of HTTP.

#### Direct HTTP/MCP Protocol

You can also connect directly using the MCP protocol over HTTP:

```bash
# Test the connection
curl http://localhost:8002/mcp
```

## ⚙️ Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `ws://localhost:8000` | AI Explorer API WebSocket URL |
| `HTTP_HOST` | `0.0.0.0` | HTTP server host |
| `HTTP_PORT` | `8002` | HTTP server port |
| `SERVER_NAME` | `ai-explorer-mcp-external` | MCP server name |
| `SERVER_VERSION` | `0.1.0` | MCP server version |
| `WEBSOCKET_TIMEOUT` | `300` | WebSocket timeout (seconds) |
| `REQUEST_TIMEOUT` | `120` | Request timeout (seconds) |
| `LOG_LEVEL` | `INFO` | Logging level |

## 🏗️ Architecture

```
AI Agent MCP Server
├── 🔌 MCP Protocol Interface
├── 🛠️  Tools (ask_explorer)
├── 🌐 WebSocket Client
└── ⚙️  Configuration

     ↓ WebSocket Connection
     
AI Explorer Backend API
├── 🤖 LLM Orchestrator
├── 📊 Hedera Data Sources
└── 🧠 AI Analysis Engine
```

## 🔧 Development

### Project Structure

```
mcp_external/
├── main.py              # MCP server entry point
├── app/
│   ├── __init__.py
│   ├── main.py          # FastMCP server with tool definitions
│   ├── logging_config.py # Logging configuration
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py  # Configuration management
│   └── client/
│       ├── __init__.py
│       └── api_client.py # WebSocket client for AI Explorer API
├── pyproject.toml       # Project configuration
└── README.md           # This file
```

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Code Quality

```bash
# Format code
black mcp_external/

# Lint code
ruff check mcp_external/
```

## 🔒 Security Considerations

- **Authentication**: Currently uses direct WebSocket connection. API key authentication planned for production.
- **Rate Limiting**: Inherits rate limiting from the underlying AI Explorer API
- **Input Validation**: Validates account ID format and network parameters
- **Error Handling**: Safely handles API errors and connection issues

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is part of the AI Explorer ecosystem. See the main project license for details.

## 🆘 Support

For issues and questions:
1. Check the AI Explorer backend logs
2. Verify WebSocket connectivity to the API
3. Ensure proper MCP client configuration
4. Open an issue in the main AI Explorer repository

## 🔮 Roadmap

- [ ] API key authentication
- [ ] Streaming responses for long queries
- [ ] Additional specialized tools (account analysis, transaction monitoring)
- [ ] Metrics and monitoring
- [ ] Docker containerization