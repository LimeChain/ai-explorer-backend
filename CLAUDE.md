# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the backend for "THF AI Explorer" - a next-generation block explorer for the Hedera network that enables users to consume and understand on-chain data through natural language queries. The system translates raw blockchain data into human-readable "Smart View" summaries using Large Language Models (LLMs).

## Architecture Overview

The system follows a multi-container architecture with the following key components:

- **Frontend Application**: React-based SPA for user interface
- **API Gateway**: Entry point handling routing and cost-based rate limiting
- **Backend Service**: Core AI agent built with Python, FastAPI, and LangGraph
- **MCP Servers**: BigQuery and Hedera SDK data fetching services
- **Database**: PostgreSQL for session-based chat history
- **Cache**: Redis for rate limiting and session management

## Key Technical Decisions

### Multi-Chain Extensibility

The entire system is designed with blockchain abstraction in mind to support future chains with minimal refactoring:

- Data source abstraction layer separates BigQuery/SDK logic
- Wallet integration abstraction (currently HashPack only)
- Common internal data format for transaction summarization

### Cost-Based Rate Limiting

Rate limiting is based on estimated costs of downstream services (LLM + BigQuery), not just request counts, to provide fine-grained budget control.

### Anonymous Session-Based History

Chat history is stored anonymously with temporary session IDs (not linked to wallet addresses) for GDPR compliance and privacy.

### Security Philosophy

"Zero Trust for AI" model - all user input and LLM output is treated as untrusted until explicitly verified.

## Development Environment

This repository is currently in the initial planning phase with no source code implementation yet. The project exists only as documentation (BRD and SDD).

## Current Repository Status

- **Implementation Phase**: Pre-development (documentation only)
- **Available Files**: BRD.md, SDD.md, CLAUDE.md, README.md (empty)
- **No build files, package managers, or source code present**

## Planned Tech Stack (From SDD)

- **Backend**: Python + FastAPI + LangGraph
- **Database**: PostgreSQL
- **Cache**: Redis
- **Containerization**: Docker
- **Cloud**: Google Cloud Run
- **Infrastructure**: Terraform
- **CI/CD**: GitHub Actions
- **MCP Servers**: BigQuery MCP Server, Hedera SDK MCP Server

## Development Commands

*Note: These commands will be available once the project implementation begins*

### Expected Future Commands
- `uv venv venv` - Create virtual environment
- `uv sync` - Install dependencies
- `uv run uvicorn app.main:app --reload --port 8000` - Run FastAPI development server
- `uv run pytest` - Run tests
- `docker-compose up` - Run full stack locally
- `terraform plan` - Preview infrastructure changes

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

## Future Development Notes

When implementing this system:

1. Use LangSmith for logging (as recommended in SDD)
2. Implement token-by-token streaming for responses
3. Design wallet connection module for easy extensibility
4. Create abstraction layers for multi-chain support
5. Implement comprehensive logging for debugging and metrics
6. Consider user feedback mechanism (thumbs up/down) for response quality

## Documentation References

- `/docs/BRD.md` - Business Requirements Document with detailed functional requirements
- `/docs/SDD.md` - Software Design Document with complete architecture specifications
