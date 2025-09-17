# Hederion AI Explorer Backend

Hederion AI Explorer is a next-generation block explorer for the Hedera network that enables users to consume and understand on-chain data through natural language queries.

## Status

- API endpoints
  - ✅ Chat endpoint for real-time user queries and token-by-token streaming responses over WebSockets
  - ✅ Suggested queries endpoint for list of pre-defined queries
  - ✅ IP and global rate/cost limiting
- AI Agent
  - ✅ LLM agentic reasoning and tool use
  - ✅ Multi-turn conversation with context retention
  - ✅ Session-based conversations (anonymous and pseudonymous sessions)
  - ✅ Contextual user data (wallet account ID)
- Relational Database
  - ✅ Chat history with database persistence
- Vector Database
  - ✅ Semantic search with embeddings
- MCP tools
  - ✅ Hedera's Mirror Node REST API
  - ❌ Hedera's BigQuery
  - ✅ Timestamp conversion tool
  - ✅ Money value conversion tool
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
- Redis
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

Tests the rate and cost limiting by sending multiple requests to the WebSocket endpoint.

```sh
uv run python scripts/spam.py
uv run python scripts/spam.py concurrent

uv run python scripts/check_limits.py list --details   
uv run python scripts/check_limits.py stats
uv run python scripts/check_limits.py clear
uv run python scripts/check_limits.py monitor
```


### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`


## Deployment
Prod and dev environments are running in the same GCP project. 

Dev environment is deployed with default Terraform workspace while prod is deployed with prod workspace. This makes Terraform use different state files for both environments.

Before deploying check the Terraform workspace:
```sh
terraform workspace list
```

If needed change the workspace:
```sh
terraform workspace select <workspace>
```

### tfvars used for prod
```sh
project_id        = "<PROJECT_ID>>"
llm_api_key       = "<API_KEY>"
langsmith_api_key = ""
environment       = "production"
domain_name       = "hederion.com"
app_name          = "ai-explorer-prod"
```


```json
query {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      name
      kind
      description
      fields(includeDeprecated: true) {
        name
        description
        args {
          name
          description
          type {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
          defaultValue
        }
        type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
            }
          }
        }
        isDeprecated
        deprecationReason
      }
      inputFields {
        name
        description
        type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
            }
          }
        }
        defaultValue
      }
      interfaces {
        kind
        name
      }
      enumValues(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
      }
      possibleTypes {
        kind
        name
      }
    }
    directives {
      name
      description
      locations
      args {
        name
        description
        type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
            }
          }
        }
        defaultValue
      }
    }
  }
}
```