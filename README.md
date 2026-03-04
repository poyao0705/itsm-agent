# ITSM Agent

An AI-powered **IT Service Management** agent that automates change risk evaluation for GitHub Pull Requests. Built on [LangGraph](https://github.com/langchain-ai/langgraph), it listens for GitHub webhook events, runs a deterministic + AI-assisted policy analysis pipeline, and posts risk assessment comments directly on PRs.

Designed around **ISO/IEC 20000** change-control principles, the agent enforces configurable policy rules (defined in YAML) to classify every PR as LOW or HIGH risk based on the files it touches.

Demo site: [ITSM Agent](https://itsm-agent.site)

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
- **LangGraph evaluation pipeline** — a multi-node state graph that extracts PR data, validates JIRA tickets, runs LLM semantic analysis, applies policy rules, and posts comments
- **LLM-powered semantic risk audit** — compares JIRA ticket descriptions against code diffs using OpenAI to detect scope creep and unhandled risks
- **Deterministic policy engine** — YAML-driven risk classification with glob-based file path matching
- **JIRA integration** — validates ticket numbers in PR titles and fetches metadata via the JIRA API
- **Automatic PR commenting** — posts risk assessment summaries directly on pull requests via the GitHub API
- **Real-time web dashboard** — HTMX + SSE-powered UI displaying live evaluation results with pagination (latest per PR)
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
┌───────────────────────────────────────────────────────┐
│             LangGraph State Machine                   │
│                                                       │
│  read_pr_from_webhook                                 │
│       ▼                                               │
│  fetch_pr_info  (GitHub REST API)                     │
│       ▼                                               │
│  analyze_jira_ticket_number  (JIRA API validation)    │
│       ▼                                               │
│  ┌────────────────────────┬──────────────────────┐    │
│  │ jira_to_code_llm       │ policy_rule_analysis │    │
│  │ (OpenAI semantic audit)│ (YAML policy engine) │    │
│  └────────────┬───────────┴──────────┬───────────┘    │
│               ▼                      ▼                │
│              post_pr_comment  (GitHub REST API)       │
└──────────────────┬────────────────────────────────────┘
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
├── .dockerignore
├── .env.example
├── .gitignore
├── Caddyfile
├── Dockerfile
├── README.md
├── alembic.ini
├── alembic/
│   ├── README
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                        # Database migration scripts
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app entry point
│   ├── api/
│   │   ├── __init__.py
│   │   ├── api_v1.py                    # API v1 router
│   │   └── endpoints/
│   │       ├── __init__.py
│   │       ├── github.py                # GitHub webhook endpoint (signature verification, event routing)
│   │       └── health.py                # Health check endpoint
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                    # Pydantic Settings (env vars)
│   │   ├── http_client.py              # Shared async HTTP client
│   │   ├── lifespan.py                 # App startup/shutdown lifecycle
│   │   ├── llm.py                      # LLM client initialization
│   │   ├── logging.py                  # Centralized logging
│   │   └── security.py                 # HMAC SHA-256 signature verification
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py                   # Async engine & session factory
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── evaluation_run.py        # EvaluationRun ORM model
│   │       └── analysis_result.py       # AnalysisResult ORM model
│   ├── dependencies/
│   │   ├── __init__.py
│   │   └── database.py                 # FastAPI database dependency injection
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── github/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                  # GitHub App JWT authentication
│   │   │   └── client.py               # GitHub REST API client
│   │   └── jira/
│   │       ├── __init__.py
│   │       └── client.py               # JIRA REST API client
│   ├── services/
│   │   ├── __init__.py
│   │   └── change_management/
│   │       ├── __init__.py
│   │       ├── cache.py                 # In-memory evaluation cache
│   │       ├── cache_updater.py         # Background cache refresh task
│   │       ├── evaluations.py           # Evaluation orchestration service
│   │       ├── graph.py                 # LangGraph workflow definition
│   │       ├── notifier.py             # In-process asyncio notification
│   │       ├── prompts.py              # LLM prompt templates
│   │       ├── state.py                # AgentState model
│   │       ├── nodes/
│   │       │   ├── __init__.py
│   │       │   ├── pr_io.py             # Webhook parsing, PR fetch, comment posting
│   │       │   ├── analysis.py         # JIRA ticket & policy rule analysis
│   │       │   ├── llm_analysis.py     # LLM semantic risk audit (JIRA vs code diff)
│   │       │   └── utils.py            # Shared node utilities (make_result)
│   │       └── policy/
│   │           ├── __init__.py
│   │           ├── policy.yaml          # Risk classification rules
│   │           ├── loader.py            # YAML policy loader
│   │           ├── types.py            # ChangeTypeRule data model
│   │           └── priority.py         # Risk priority helpers
│   ├── web/
│   │   ├── __init__.py
│   │   └── router.py                   # HTMX pages & SSE stream endpoints
│   ├── templates/
│   │   ├── base.html                    # Base layout template
│   │   ├── evaluations.html             # Evaluations page template
│   │   ├── index.html                   # Home page template
│   │   └── partials/
│   │       ├── dashboard.html           # Dashboard partial
│   │       ├── evaluations_latest.html  # Latest evaluations partial
│   │       └── evaluations_list.html    # Evaluations list partial
│   └── static/
│       ├── css/
│       │   └── vendor/                  # Vendored CSS (DaisyUI)
│       └── js/
│           └── vendor/                  # Vendored JS (HTMX, Alpine.js, Tailwind CSS)
├── docs/
│   └── SETUP_GUIDE.md
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Pytest fixtures & shared test setup
│   ├── test_cache.py                    # Cache tests
│   ├── test_evaluations.py             # Evaluation service tests
│   ├── test_github_auth.py             # GitHub auth tests
│   ├── test_github_client.py           # GitHub client tests
│   ├── test_jira_client.py             # JIRA client tests
│   ├── test_nodes.py                   # LangGraph node tests
│   ├── test_security.py               # HMAC security tests
│   └── test_webhook_service.py         # Webhook service tests
├── docker-compose.yaml
├── pyproject.toml
└── uv.lock
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

# JIRA
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token

# GitHub App
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY=/path/to/private-key.pem   # or inline PEM string
GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

| Variable                 | Required | Description                                                                 |
| ------------------------ | -------- | --------------------------------------------------------------------------- |
| `DATABASE_URL`           | Yes      | Async PostgreSQL connection string (`postgresql+asyncpg://...`)             |
| `OPENAI_API_KEY`         | Yes      | OpenAI API key for LLM-based semantic risk analysis                        |
| `JIRA_BASE_URL`          | Yes      | JIRA instance URL (e.g. `https://your-domain.atlassian.net`)               |
| `JIRA_EMAIL`             | Yes      | Email associated with the JIRA API token                                   |
| `JIRA_API_TOKEN`         | Yes      | JIRA API token for ticket validation                                       |
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

- **Home** — shows the latest evaluation per PR with real-time SSE updates
- **Evaluations** (`/evaluations`) — paginated list of latest evaluations per PR with risk levels, statuses, and analysis details

The dashboard updates in real-time via Server-Sent Events without polling the database — a background cache updater task refreshes an in-memory cache, and all connected SSE clients receive updates simultaneously.