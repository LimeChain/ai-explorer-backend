# AI Explorer Backend

Backend service for the THF AI Explorer - a next-generation block explorer for the Hedera network that enables users to consume and understand on-chain data through natural language queries.

## Overview

This is the foundational backend service that provides a hardcoded `/chat` endpoint for the AI Explorer. The service is built with FastAPI and will eventually integrate with Large Language Models (LLMs) to translate raw blockchain data into human-readable "Smart View" summaries.

## Features

- RESTful API with FastAPI
- Pydantic models for request/response validation
- Structured logging
- Docker containerization with multi-stage builds
- Health check endpoint

## Local Development Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key

### Configuration

1. Create a `.env` file in the root directory:
```bash
cp .env .env.local
```

2. Edit `.env.local` and add your configuration:
```bash
# API Keys
OPENAI_API_KEY=your_actual_openai_api_key_here


# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO

# Database (for local development)
DATABASE_URL=postgresql://ai_explorer:ai_explorer@localhost:5433/ai_explorer

# MCP Server
MCP_ENDPOINT=http://localhost:8001/mcp/
```

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-explorer-backend
```

2. Install dependencies using uv & activate venv:
```bash
uv sync
```

### Database Setup

3. Start the PostgreSQL database:
```bash
docker-compose up postgres
```

4. Run database migrations:
```bash
alembic upgrade head
```

5. Run the development server:
```

### Database Setup

3. Start the PostgreSQL database:
```bash
docker-compose up postgres
```

4. Run database migrations:
```bash
alembic upgrade head
```

5. Run the development server:
```bash
uv run uvicorn app.main:app --reload --port 8000
```

The service will be available at `http://localhost:8000`.


6. Install the SDK as a package:
```bash

cd mcp_servers

uv pip install -e ../sdk
```

7. Run the MCP server:
```bash
cd .. # Go back to root

uv run python mcp_servers/main.py
```

### Database Management

#### Database Migration Commands

Create a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Check migration status:
7. Run the MCP server:
```bash
cd .. # Go back to root

uv run python mcp_servers/main.py
```

### Database Management

#### Database Migration Commands

Create a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Check migration status:
```bash
alembic current
```

#### Database Features

The backend includes:
- **GDPR-compliant chat history**: Anonymous session-based storage
- **Conversation persistence**: Messages are saved with timestamps
- **Session management**: Conversations are tracked by session ID
- **Account context**: Optional account ID for personalized responses

#### Database Schema

- **conversations**: Stores session information and optional account context
- **messages**: Stores individual user and assistant messages within conversations
alembic current
```

#### Database Features

The backend includes:
- **GDPR-compliant chat history**: Anonymous session-based storage
- **Conversation persistence**: Messages are saved with timestamps
- **Session management**: Conversations are tracked by session ID
- **Account context**: Optional account ID for personalized responses

#### Database Schema

- **conversations**: Stores session information and optional account context
- **messages**: Stores individual user and assistant messages within conversations

### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Usage

### WebSocket Chat Endpoint

The chat functionality uses WebSocket connections for real-time streaming responses. Connect to the WebSocket endpoint at `/api/v1/chat/ws` and send JSON messages.

#### Using Postman (Recommended)

1. **Create a new WebSocket request in Postman**:
   - Set URL to: `ws://localhost:8000/api/v1/chat/ws`
   - Click "Connect"

2. **Send a simple query**:
   ```json
   {
     "query": "What is the Hedera network?"
   }
   ```

3. **Send a query with wallet context**:
   ```json
   {
     "query": "What is my wallet address?",
     "account_id": "0.0.12345",
     "session_id": "client-session-123"
   }
   ```

4. **Send a multi-turn conversation**:
   ```json
   {
     "messages": [
       {"role": "user", "content": "Tell me about Hedera"},
       {"role": "assistant", "content": "Hedera is a distributed ledger..."},
       {"role": "user", "content": "What about its consensus mechanism?"}
     ],
     "account_id": "0.0.12345",
     "session_id": "client-session-456"
   }
   ```

#### Message Format

**Request (Client → Server):**
```json
{
  "query": "your question here",              // OR "messages": [...]
  "account_id": "0.0.12345",                 // Optional: connected wallet
  "session_id": "client-session-123"         // Optional: for traceability
}
```

**Response (Server → Client):**
```json
{"token": "The"}
{"token": " Hedera"}
{"token": " network"}
{"token": " is"}
...
{"complete": true}
```

**Error Response:**
```json
{"error": "Invalid request: Query cannot be empty"}
```

#### Using curl (Alternative)

For testing with curl, you can use a WebSocket client like `wscat`:

```bash
# Install wscat if you don't have it
npm install -g wscat

# Connect and send a message
wscat -c ws://localhost:8000/api/v1/chat/ws

# Then send:
{"query": "What is the Hedera network?"}
```

### Health Check

Check if the service is running:

```bash
curl http://localhost:8000/
```

## Docker Deployment

### Build the Docker image:
```bash
docker build -t ai-explorer-backend .
```

### Run the container:
```bash
docker run -p 8000:8000 ai-explorer-backend
```

### Test the containerized service:
```bash
# Use wscat to test WebSocket connection
wscat -c ws://localhost:8000/api/v1/chat/ws

# Then send:
{"query": "test from docker"}
```

**Note:** You'll need to pass your OpenAI API key as an environment variable when running the container:
```bash
docker run -p 8000:8000 -e OPENAI_API_KEY=your_api_key_here ai-explorer-backend
```

## Development Status

This implementation includes:
- ✅ LLM integration with streaming responses using LangChain
- ✅ Token-by-token streaming via WebSocket connections
- ✅ Contextual user data support (account ID integration)
- ✅ Contextual user data support (account ID integration)
- ✅ Multi-turn conversation support
- ✅ Configuration management with environment variables
- ✅ Structured logging and error handling
- ✅ **Database persistence with PostgreSQL**
- ✅ **GDPR-compliant chat history storage**
- ✅ **Session-based conversation tracking**
- ✅ **Database migrations with Alembic**
- ✅ **Database persistence with PostgreSQL**
- ✅ **GDPR-compliant chat history storage**
- ✅ **Session-based conversation tracking**
- ✅ **Database migrations with Alembic**

Future iterations will include:
- BigQuery integration for Hedera network data
- Hedera SDK integration for real-time data
- Authentication and rate limiting
- Cost-based budget limiting
- Chat history retrieval endpoints
- Chat history retrieval endpoints