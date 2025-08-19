# Hederion AI Explorer Backend

Hederion AI Explorer is a next-generation block explorer for the Hedera network that enables users to consume and understand on-chain data through natural language queries.

## Status

- REST API
  - ✅ Chat endpoint for real-time user queries and token-by-token streaming responses over WebSockets.
  - ✅ Suggested queries endpoint for list of pre-defined queries
  - ✅ IP and global rate limiting for protecting the API
  - [ ] Cost-based limits
  - [ ] Chat history retrieval endpoint for retrieving previous conversations
- AI Agent
  - ✅ LLM agentic reasoning
  - ✅ Multi-turn conversation
  - ✅ Session-based conversations (anonymous and pseudonymous sessions)
  - ✅ Contextual user data (wallet account ID)
- Storage
  - ✅ GDPR-compliant chat history with database persistence
- MCP Servers
  - ✅ Hedera's REST API for real-time data
  - [ ] Hedera's BigQuery for historical data
- Benchmarking
  - ✅ Tracing
  - ✅ Evaluations
- [ ] Unit & Integration Tests
- ✅ CI/CD
- ✅ Documentation


## Setup

### Prerequisites

- Docker, Docker Compose
- [uv](https://docs.astral.sh/uv/) package manager
- Python 3.13+
- PostgreSQL
- LLM API (OpenAI, Google, etc.)


### Run Locally

1. Clone the repository:
```bash
git clone https://github.com/LimeChain/ai-explorer-backend
cd ai-explorer-backend
```

2. Create `.env` file and configure the necessary environment variables:
```bash
cp .env.example .env
```

3. Install dependencies:
```bash
uv sync
```

4. Start the database:
```bash
docker compose up db
```

5. Run database migrations:
```bash
uv run alembic upgrade head
```

6. Start the API server:
```bash
uv run uvicorn app.main:app --reload --port 8000
```

7. Install the Hedera SDK as a package and start the MCP server:
```bash
uv pip install -e ./sdk
uv run python mcp_servers/main.py
```

8. Send a sample query over WebSocket:
```bash
uv run python scripts/ws_send_query.py
```


### Run Locally (with Docker)

1. Configure the `.env` file to use the correct mcp endpoint:

2. Start all services with Docker:
```bash
docker compose up
```

3. Send a sample query over WebSocket:
```bash
docker compose exec api uv run python scripts/dev/query_websocket_dev.py
```


### Development

#### Database Management

Create a new migration:
```bash
uv run alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
uv run alembic upgrade head
```

### Enable Tracing

Configure the LangSmith tracing in the `.env` file.

### Run Evaluations

```bash
uv run python -m evals.main
```


## Testing

### Spamming the WebSocket endpoint

Tests the rate limiting by sending multiple requests to the WebSocket endpoint.

```sh
python scripts/spam_websocket.py
python scripts/spam_websocket.py concurrent
```

Monitors and manages rate limiting data stored in Redis.

```sh
python scripts/check_redis_counters.py list
python scripts/check_redis_counters.py list --details --requests
python scripts/check_redis_counters.py monitor
python scripts/check_redis_counters.py monitor 3
python scripts/check_redis_counters.py stats
python scripts/check_redis_counters.py clear
```


### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

