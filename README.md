# ITSM Agent

An AI-powered **IT Service Management** agent that automates change risk evaluation for GitHub Pull Requests. Built on [LangGraph](https://github.com/langchain-ai/langgraph), it listens for GitHub webhook events, runs a deterministic + AI-assisted policy analysis pipeline, and posts risk assessment comments directly on PRs.

Designed around **ISO/IEC 20000** change-control principles, the agent enforces configurable policy rules (defined in YAML) to classify every PR as LOW or HIGH risk based on the files it touches.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Getting Started](#getting-started)
  - [Local Development](#local-development)
  - [Docker (Production)](#docker-production)
- [Database Migrations](#database-migrations)
- [Policy Configuration](#policy-configuration)
- [API Reference](#api-reference)
- [Web Dashboard](#web-dashboard)

---

## Features

- **GitHub App webhook integration** — receives `pull_request` events and processes them automatically
- **LangGraph evaluation pipeline** — a multi-node state graph that extracts PR data, validates JIRA tickets, applies policy rules, and posts comments
- **Deterministic policy engine** — YAML-driven risk classification with glob-based file path matching
- **Automatic PR commenting** — posts risk assessment summaries directly on pull requests via the GitHub API
- **Real-time web dashboard** — HTMX + SSE-powered UI displaying live evaluation results with pagination
- **Async PostgreSQL persistence** — stores evaluation runs and analysis results with full audit trail
- **Idempotent evaluations** — deduplicates by `owner/repo:pr_number:head_sha:body_hash`
- **In-memory cache with SSE push** — a single background task refreshes an in-memory cache; all SSE clients share the result with zero per-client DB load

---

## Architecture

```
GitHub Webhook (pull_request)
        │
        ▼
┌───────────────────────┐
│  FastAPI Application  │
│  POST /api/v1/github  │
│       /webhook        │
└──────────┬────────────┘
           │  verify HMAC signature
           ▼
┌───────────────────────────────────────────────┐
│          LangGraph State Machine              │
│                                               │
│  read_pr_from_webhook                         │
│       ▼                                       │
│  fetch_pr_info  (GitHub REST API)             │
│       ▼                                       │
│  analyze_jira_ticket_number                   │
│       ▼                                       │
│  policy_rule_analysis  (YAML policy engine)   │
│       ▼                                       │
│  post_pr_comment  (GitHub REST API)           │
└──────────────────┬────────────────────────────┘
                   │
                   ▼
┌──────────────────────┐      ┌─────────────────────┐
│   PostgreSQL (async) │◄────►│  Web Dashboard      │
│   evaluation_run     │      │  HTMX + SSE         │
│   analysis_result    │      │  /evaluations       │
└──────────────────────┘      └─────────────────────┘
```

---

## Tech Stack

| Layer            | Technology                                       |
| ---------------- | ------------------------------------------------ |
| Web Framework    | FastAPI + Uvicorn                                |
| AI Orchestration | LangGraph / LangChain / OpenAI                   |
| Database         | PostgreSQL (asyncpg + SQLAlchemy + SQLModel)     |
| Migrations       | Alembic                                          |
| GitHub Auth      | GitHub App (JWT + installation tokens via PyJWT) |
| Frontend         | Jinja2 templates + HTMX + SSE (sse-starlette)    |
| Reverse Proxy    | Caddy (automatic HTTPS)                          |
| Package Manager  | uv                                               |
| Containerisation | Docker + Docker Compose                          |

---

## Project Structure

```
├── app/
│   ├── main.py                        # FastAPI app entry point
│   ├── api/
│   │   ├── api_v1.py                  # API v1 router
│   │   └── endpoints/
│   │       ├── github.py              # GitHub webhook endpoint
│   │       └── health.py              # Health check endpoint
│   ├── core/
│   │   ├── config.py                  # Pydantic Settings (env vars)
│   │   ├── lifespan.py               # App startup/shutdown lifecycle
│   │   ├── logging.py                # Centralized logging
│   │   ├── cache_updater.py          # Background cache refresh task
│   │   ├── evaluation_cache.py       # In-memory evaluation cache
│   │   └── notifier.py              # In-process asyncio notification
│   ├── db/
│   │   ├── session.py                 # Async engine & session factory
│   │   └── models/
│   │       ├── evaluation_run.py      # EvaluationRun ORM model
│   │       └── analysis_result.py     # AnalysisResult ORM model
│   ├── integrations/
│   │   └── github/
│   │       ├── auth.py                # GitHub App JWT authentication
│   │       └── client.py             # GitHub REST API client
│   ├── services/
│   │   ├── change_management/
│   │   │   ├── graph.py               # LangGraph workflow definition
│   │   │   ├── state.py              # AgentState model
│   │   │   ├── context.py            # LangGraph runtime context (DI)
│   │   │   ├── evaluations.py        # Evaluation orchestration service
│   │   │   ├── nodes/
│   │   │   │   ├── pr_io.py           # Webhook parsing, PR fetch, comment posting
│   │   │   │   └── analysis.py       # JIRA ticket & policy rule analysis
│   │   │   └── policy/
│   │   │       ├── policy.yaml        # Risk classification rules
│   │   │       ├── loader.py          # YAML policy loader
│   │   │       ├── types.py          # ChangeTypeRule data model
│   │   │       └── priority.py       # Risk priority helpers
│   │   └── github/
│   │       ├── webhook_service.py     # Webhook dispatch & signature verification
│   │       └── security.py           # HMAC SHA-256 signature verification
│   ├── web/
│   │   └── router.py                 # HTMX pages & SSE stream endpoints
│   ├── templates/                     # Jinja2 HTML templates
│   └── static/                        # CSS & JS assets
├── alembic/                           # Database migration scripts
├── docs/                              # Documentation & specs
├── docker-compose.yaml
├── Dockerfile
├── Caddyfile
├── pyproject.toml
└── alembic.ini
```

---

## Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager
- **PostgreSQL** — local instance or managed service
- **GitHub App** — with webhook configured for `pull_request` events
- **OpenAI API key**

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/itsm_agent

# OpenAI
OPENAI_API_KEY=sk-...

# GitHub App
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY=/path/to/private-key.pem   # or inline PEM string
GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

| Variable                 | Required | Description                                                                 |
| ------------------------ | -------- | --------------------------------------------------------------------------- |
| `DATABASE_URL`           | Yes      | Async PostgreSQL connection string (`postgresql+asyncpg://...`)             |
| `OPENAI_API_KEY`         | Yes      | OpenAI API key for LLM-based analysis                                      |
| `GITHUB_APP_ID`          | Yes      | Your GitHub App's ID                                                        |
| `GITHUB_APP_PRIVATE_KEY` | Yes      | Path to PEM file **or** inline key (escaped `\n` supported)                |
| `GITHUB_WEBHOOK_SECRET`  | Yes      | Secret used to verify webhook HMAC signatures                              |

> **Note:** `GITHUB_APP_PRIVATE_KEY` accepts either a file path or an inline PEM string. When using a file path, the app reads the file at startup.

---

## Getting Started

### Local Development

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-org/itsm-agent.git
   cd itsm-agent
   ```

2. **Install dependencies with uv**

   ```bash
   uv sync
   ```

3. **Set up the environment**

   ```bash
   cp .env.example .env   # or create .env manually (see Environment Variables above)
   ```

4. **Start PostgreSQL**

   Use an existing instance, or uncomment the `db` service in `docker-compose.yaml` for a local container:

   ```bash
   docker compose up db -d
   ```

5. **Run database migrations**

   ```bash
   uv run alembic upgrade head
   ```

6. **Start the development server**

   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   The app is now available at **http://localhost:8000**.

### Docker (Production)

The production setup uses Docker Compose with Caddy as the reverse proxy (automatic HTTPS).

1. **Prepare the environment**

   ```bash
   # Place your GitHub App private key in the project root
   cp /path/to/private-key.pem ./pr-comment-bot-key.2026-01-28.pem

   # Create .env with all required variables
   ```

2. **Build and start**

   ```bash
   docker compose up -d --build
   ```

   This starts:
   - **backend** — the FastAPI application on port 8000 (internal)
   - **caddy** — reverse proxy on ports 80/443 with automatic TLS

3. **Run migrations** (first time or after model changes)

   ```bash
   docker compose exec backend alembic upgrade head
   ```

4. **Check health**

   ```bash
   curl https://your-domain.com/api/v1/health
   # {"status": "ok"}
   ```

---

## Database Migrations

Migrations are managed by **Alembic** with async PostgreSQL support.

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Create a new migration after model changes
uv run alembic revision --autogenerate -m "describe your change"

# Downgrade one revision
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

---

## Policy Configuration

Risk classification rules are defined in [`app/services/change_management/policy/policy.yaml`](app/services/change_management/policy/policy.yaml). The policy engine uses **glob-based file path matching** to determine risk levels.

Example:

```yaml
risk_levels:
  LOW:
    description: "Low risk change"
    change_types: {}

  HIGH:
    description: "High risk change"
    change_types:
      db:
        description: "Database changes"
        path_patterns:
          - "alembic/migrations/**"
          - "app/db/**"
      infra:
        description: "Infrastructure changes"
        path_patterns:
          - "Dockerfile"
          - "docker-compose.yaml"
```

When a PR's changed files match a HIGH-risk path pattern, the agent flags the PR accordingly and posts a risk summary as a PR comment.

The agent also checks for a **JIRA ticket number** (pattern `ABC-1234`) in the PR title. Missing tickets are flagged as HIGH risk.

---

## API Reference

| Method | Endpoint                        | Description                              |
| ------ | ------------------------------- | ---------------------------------------- |
| GET    | `/api/v1/health`                | Health check                             |
| POST   | `/api/v1/github/webhook`        | GitHub webhook receiver                  |
| GET    | `/`                             | Web dashboard (HTML)                     |
| GET    | `/evaluations`                  | Paginated evaluations list (HTML)        |
| GET    | `/evaluations/sse-stream`       | SSE stream for real-time eval updates    |

### Webhook Headers

The GitHub webhook endpoint expects:

| Header                  | Description                     |
| ----------------------- | ------------------------------- |
| `X-GitHub-Event`        | Event type (e.g. `pull_request`) |
| `X-Hub-Signature-256`   | HMAC SHA-256 signature          |

---

## Web Dashboard

The app includes an HTMX-powered web dashboard at the root URL (`/`):

- **Home** — shows the 5 most recent evaluations with real-time SSE updates
- **Evaluations** (`/evaluations`) — paginated list of all evaluation runs with risk levels, statuses, and analysis details

The dashboard updates in real-time via Server-Sent Events without polling the database — a background cache updater task refreshes an in-memory cache, and all connected SSE clients receive updates simultaneously.