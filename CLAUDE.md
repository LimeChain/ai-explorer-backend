# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the backend for "THE AI Explorer" - a next-generation block explorer for the Hedera network that enables users to consume and understand on-chain data through natural language queries. The system translates raw blockchain data into human-readable "Smart View" summaries using Large Language Models (LLMs).

## Architecture Overview

The system architecture follows a multi-container architecture with the following key components:

- **Frontend Application**: React-based SPA for user interface (separate repository)
- **Load Balancer**: Load balances requests to the backend API over http and websocket
- **API**: handles routing, core AI agentic workflow, cost and rate limiting and communicates with MCP over VPC
- **MCP External**: Exposes the AI Explorer to other AI agents as tools over MCP protocol
- **MCP Internal**: Provides internal tools for data fetching from Hedera Mirror Node and BigQuery.
- **Database**: PostgreSQL with pgvector extension for vector search and session-based chat history.
- **In-Memory Storage**: Redis for rate and budget limiting.
- **VPC**: Private VPC with private IP address for the API and MCP to communicate with the database and redis over VPC.

## Key Technical Decisions

### Multi-Chain Extensibility

The entire system is designed with blockchain abstraction in mind to support future chains with minimal refactoring:

- Data source abstraction layer separates REST API and BigQuery logic

### Cost-Based Rate Limiting

Rate limiting is based on estimated costs of downstream services (LLM + BigQuery), not just request counts, to provide fine-grained budget control.

### Anonymous Session-Based History

Chat history is stored anonymously with temporary session IDs (not linked to wallet addresses) for GDPR compliance and privacy.

### Security Philosophy

"Zero Trust for AI" model - all user input and LLM output is treated as untrusted until explicitly verified.

## Tech Stack

- **Backend**: Python + FastAPI + LangGraph
- **Database**: PostgreSQL
- **Cache**: Redis
- **Containerization**: Docker
- **Cloud**: GCP
- **Infrastructure**: Terraform
- **CI/CD**: GitHub Actions
- **MCP Servers**: Hedera Mirror Node MCP Server, BigQuery MCP Server

## Core Features (Phase 1 MVP)

1. **Natural Language Chat Interface** - Chat-style interface for blockchain queries
2. **Smart View Summarization** - Translate raw transaction data into human-readable summaries
3. **HashPack Wallet Integration** - Connect wallet for personalized responses
4. **BigQuery Integration** - Query historical Hedera data
5. **Real-time Data via Hedera SDK** - Fetch current network state
6. **Default Dashboard** - Display key Hedera ecosystem metrics

## Security Considerations

- System prompt-based security for malicious intent detection
- Input token limiting and request count rate limiting
- Cost-based budget limiting to prevent expensive queries
- Output sanitization to prevent XSS attacks
- Private network deployment with secret management

## Deployment Strategy

- **Containerization**: Docker with multi-stage builds
- **CI/CD**: GitHub Actions for automated deployment
- **Cloud Hosting**: Google Cloud Run for serverless deployment
- **Infrastructure as Code**: Terraform for cloud resources

## Documentation References

- `/docs/BRD.md` - Business Requirements Document with detailed functional requirements
- `/docs/SDD.md` - Software Design Document with complete architecture specifications
