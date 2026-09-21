# AgentSphere AI Backend

This directory contains the backend-only implementation of AgentSphere AI, an enterprise agentic AI platform for B2B customer discovery and prospect intelligence.

The backend accepts an ICP, target personas, and business triggers, then executes a multi-agent workflow that discovers companies, validates them, enriches contacts, generates a structured sales intelligence report, streams execution logs, and pauses for human approval.

## Current Backend Status

Implemented backend components:

- FastAPI application with async REST APIs, WebSocket route, CORS, lifespan startup/shutdown, and `/health`.
- Clerk JWT authentication with JWKS caching.
- LangGraph workflow state and graph definition.
- In-process async workflow execution via FastAPI background tasks.
- MongoDB document store for workflows, companies, contacts, and logs.
- Redis cache, locks, pub/sub, event buffers, and Celery broker/backend.
- Pinecone vector memory integration with local fallback when Pinecone is unavailable.
- OpenAI GPT-4o planner and summary integration with deterministic fallback when OpenAI or `langchain-openai` is unavailable.
- External service clients for Serper, Crunchbase, Hunter, and Apollo.
- Agent implementations for planner, search, company discovery, validation, decision maker lookup, contact enrichment, summary, and human approval.
- Backend tests for core agent behavior, memory helpers, workflow schemas, and workflow router CRUD.
- Interpreter-safe startup scripts to avoid using global Python by accident.

Important runtime note:

Use the scripts in `backend/scripts/` or the explicit `./venv/bin/python -m ...` commands. If you run global `uvicorn`, it may use Homebrew Python and fail with errors such as `ModuleNotFoundError: No module named 'redis'`.

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| API | FastAPI | REST API, WebSocket, health endpoint, docs |
| ASGI server | Uvicorn | Runs FastAPI locally and in containers |
| Validation | Pydantic v2 | Request and response schemas |
| Settings | pydantic-settings | Environment-based config |
| Auth | Clerk JWT, python-jose | User identity and role checks |
| Workflow engine | LangGraph | Stateful agent graph execution |
| LLM | OpenAI GPT-4o | Planner and Summary agents |
| Embeddings | OpenAI `text-embedding-3-small` | Company vector memory |
| Database | MongoDB via motor | Persistent workflow data |
| Cache and events | Redis via redis.asyncio | Cache, locks, sessions, pub/sub |
| Background jobs | Celery | Long-running workflow execution |
| Vector store | Pinecone | Semantic memory and deduplication |
| HTTP client | httpx | External API calls |
| Tests | pytest, pytest-asyncio | Backend test suite |

## Folder Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── exceptions.py
│   │   └── security.py
│   ├── schemas/
│   │   ├── agent.py
│   │   ├── company.py
│   │   ├── contact.py
│   │   └── workflow.py
│   ├── routers/
│   │   ├── agents.py
│   │   ├── auth.py
│   │   ├── memory.py
│   │   ├── websockets.py
│   │   └── workflows.py
│   ├── agents/
│   │   ├── planner_agent.py
│   │   ├── search_agent.py
│   │   ├── company_discovery_agent.py
│   │   ├── validation_agent.py
│   │   ├── decision_maker_agent.py
│   │   ├── contact_enrichment_agent.py
│   │   ├── summary_agent.py
│   │   └── human_approval_agent.py
│   ├── graph/
│   │   ├── state.py
│   │   ├── nodes.py
│   │   └── workflow_graph.py
│   ├── memory/
│   │   ├── cache.py
│   │   ├── document_store.py
│   │   └── vector_store.py
│   ├── services/
│   │   ├── apollo_service.py
│   │   ├── common.py
│   │   ├── crunchbase_service.py
│   │   ├── hunter_service.py
│   │   ├── serper_service.py
│   │   └── workflow_executor.py
│   ├── tools/
│   │   ├── email_finder_tool.py
│   │   ├── linkedin_tool.py
│   │   ├── phone_finder_tool.py
│   │   └── web_search_tool.py
│   └── domain/
│       └── domain_profile.py
├── scripts/
│   └── run_api.sh
├── tests/
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Core Runtime Flow

1. Client calls `POST /api/v1/workflows`.
2. FastAPI validates the payload with Pydantic.
3. Clerk JWT is verified from `Authorization: Bearer <token>`.
4. A workflow document is created in MongoDB.
5. Workflow status is set to `running`.
6. A Celery task is dispatched.
7. Celery initializes MongoDB, Redis, Pinecone/OpenAI integrations when available.
8. Celery builds the LangGraph workflow.
9. LangGraph runs agents in this order:
   - Planner Agent
   - Search Agent
   - Company Discovery Agent
   - Validation Agent
   - Decision Maker Agent
   - Contact Enrichment Agent
   - Summary Agent
   - Human Approval Agent
10. Agents write execution events to MongoDB and Redis.
11. WebSocket clients receive events from Redis pub/sub.
12. Workflow pauses with status `awaiting_approval`.
13. Client calls `POST /api/v1/workflows/{workflow_id}/approve`.
14. Contacts are approved, rejected, or edited.
15. Workflow status becomes `completed`.

## Agent Responsibilities

### Planner Agent

File: `app/agents/planner_agent.py`

Input:

- ICP configuration
- personas
- trigger list
- Redis session memory

Behavior:

- Uses GPT-4o through `langchain-openai` when installed and `OPENAI_API_KEY` is set.
- Falls back to a deterministic local plan when OpenAI is unavailable.
- Returns agent order, search queries, parallel groups, scoring weights, and token budgets.
- Tracks token count and estimated LLM cost when OpenAI is used.

### Search Agent

File: `app/agents/search_agent.py`

Behavior:

- Reads search queries from the planner output.
- Uses Serper for Google News and web search when `SERPER_API_KEY` is set.
- Caches search results in Redis for 24 hours.
- Detects business triggers with regex patterns.
- Emits `result` WebSocket events for company signals.

Supported trigger types:

- `funding_round`
- `headcount_growth`
- `new_executive`
- `product_launch`
- `expansion`

### Company Discovery Agent

File: `app/agents/company_discovery_agent.py`

Behavior:

- Reads raw search signals.
- Uses Crunchbase when `CRUNCHBASE_API_KEY` is set.
- Scores companies against ICP.
- Uses Redis locks to prevent duplicate writes.
- Checks vector memory for semantic duplicates.
- Keeps companies with `icp_match_score >= 0.65`.

ICP scoring formula:

```text
icp_score =
  industry_match * 0.25 +
  headcount_match * 0.20 +
  funding_stage_match * 0.20 +
  geography_match * 0.15 +
  revenue_match * 0.10 +
  tech_stack_match * 0.10
```

### Validation Agent

File: `app/agents/validation_agent.py`

Behavior:

- Checks whether the company domain is active.
- Calculates confidence score from source agreement, data recency, and ICP score.
- Assigns `validated`, `partial`, or `unverified`.
- Saves companies to MongoDB.
- Stores company embeddings in Pinecone or local fallback vector memory.
- Emits `progress` events.

### Decision Maker Agent

File: `app/agents/decision_maker_agent.py`

Behavior:

- Searches LinkedIn-style public results through the Serper-backed LinkedIn tool.
- Matches titles against configured personas.
- Ranks people by seniority and persona priority.
- Returns top 2-3 decision makers per company.

Seniority order:

```text
C-Suite > VP > Director > Manager > Individual Contributor
```

### Contact Enrichment Agent

File: `app/agents/contact_enrichment_agent.py`

Behavior:

- Uses Hunter for work email lookup when `HUNTER_API_KEY` is set.
- Uses Apollo for phone and LinkedIn enrichment when `APOLLO_API_KEY` is set.
- Caches enriched contacts in Redis for 12 hours.
- Saves contacts to MongoDB.
- Sets `approval_status` to `pending`.

### Summary Agent

File: `app/agents/summary_agent.py`

Behavior:

- Uses GPT-4o through `langchain-openai` when available and configured.
- Falls back to deterministic local summaries when OpenAI is unavailable.
- Produces structured sales intelligence with summary, why-now context, outreach strategy, subject lines, risks, and next actions.
- Tracks token usage and estimated LLM cost when OpenAI is used.

### Human Approval Agent

File: `app/agents/human_approval_agent.py`

Behavior:

- Sets workflow status to `awaiting_approval`.
- Emits `approval_required` over WebSocket.
- Approval is completed through `POST /api/v1/workflows/{workflow_id}/approve`.
- Supports `approve`, `reject`, and `edit`.
- Emits `workflow_completed`.

## Data Stores

### MongoDB

Collections:

| Collection | Purpose |
|---|---|
| `workflows` | Workflow config, status, summary report, cost, timestamps |
| `companies` | Qualified and validated company records |
| `contacts` | Enriched decision makers and approval state |
| `agent_logs` | Persistent backend execution logs |

User data is scoped by `user_id`.

### Redis

Redis is used for:

- Celery broker and result backend.
- Search result cache.
- Contact enrichment cache.
- Session context.
- Company deduplication locks.
- Workflow event pub/sub.
- WebSocket event buffer.

Key patterns:

| Key | Purpose |
|---|---|
| `cache:search:{sha256(query)}` | Search cache, 24 hour TTL |
| `cache:contact:{domain}:{name_hash}` | Contact cache, 12 hour TTL |
| `lock:company:{domain}` | Company processing lock |
| `session:{session_id}:context` | Session memory |
| `workflow:{workflow_id}:events` | Redis pub/sub channel |
| `workflow:{workflow_id}:event_buffer` | Buffered WebSocket events |

### Pinecone And Vector Fallback

When `PINECONE_API_KEY` is set and the Pinecone package is installed, companies are stored in Pinecone namespace `companies`.

When Pinecone is missing or not configured, the backend uses an in-memory fallback vector store. This is useful for local startup and tests, but it is not persistent.

### LLM Providers & Local-First Ollama Default

AgentSphere AI defaults to **local Ollama** (`qwen2.5:7b`) for all agent reasoning:
- **Offline Capable & Zero Cost:** Eliminates token API fees for development and high-throughput discovery workflows.
- **Privacy & Compliance:** Eliminates cloud data egress for sensitive prospect lists and target company searches.
- **Structured JSON Support:** Highly reliable JSON instruction following with models like `qwen2.5:7b` or `llama3.1:8b`.

#### Setup Local Ollama
```bash
# Install Ollama (macOS/Linux/Windows)
brew install ollama  # or download from https://ollama.com

# Pull the recommended default model
ollama pull qwen2.5:7b

# Ensure Ollama daemon is running
ollama serve
```

#### Provider Configuration & Cloud Opt-In
You can configure the active LLM via `LLM_PROVIDER`:
- `LLM_PROVIDER=ollama` (default): Uses local Ollama at `OLLAMA_BASE_URL` (default `http://localhost:11434`).
- `LLM_PROVIDER=gemini`: Opt-in cloud provider with `GEMINI_API_KEY` (model: `gemini-1.5-pro` or `gemini-1.5-flash`).
- `LLM_PROVIDER=openai`: Opt-in cloud provider with `OPENAI_API_KEY` (model: `gpt-4o`).

When Ollama is unreachable or model is not pulled, agents gracefully fall back to **deterministic execution plans and reports** without crashing the workflow or API.

### Multi-Provider Sourcing & Data Quality

To eliminate repetitive results and single-provider data gaps, AgentSphere AI employs parallel multi-provider pipelines:
1. **Company Discovery:**
   - Queries **Crunchbase** (funding rounds, founded year, canonical headcount, headquarters) and **Apollo** (domain, industry, tech stack) simultaneously.
   - Merges fields with conflict detection and records explicit evidence trails (`evidence` array with `source="crunchbase+apollo"` when corroborated).
   - Enforces strict in-run domain and company name deduplication plus FAISS exact domain lookup.
2. **Decision Maker Agent:**
   - Primary: **Apollo People Search** for verified title matches.
   - Fallback: **Serper LinkedIn search** (`site:linkedin.com/in`) for executives matching ICP roles.
3. **Contact Enrichment Agent:**
   - Primary for email: **Hunter.io** pattern matching and email deliverability confidence scoring.
   - Primary for phone & fallback email: **Apollo.io**.
   - Records provider provenance: `email_source` (`"hunter"`, `"apollo"`, or `"hunter+apollo"`), `phone_source` (`"apollo"`).

## Environment Variables

Create `backend/.env` from `.env.example` and update values for your environment.

```env
APP_ENV=development
SECRET_KEY=change_me_in_production
LOG_LEVEL=INFO
MOCK_MODE=True

# LLM Configuration (Defaults to local Ollama)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# Optional Cloud LLMs (Opt-in via LLM_PROVIDER)
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Data Providers
CRUNCHBASE_API_KEY=
APOLLO_API_KEY=
HUNTER_API_KEY=
SERPER_API_KEY=

MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=agentsphere

REDIS_URL=redis://localhost:6379/0
HUNTER_API_KEY=...
APOLLO_API_KEY=...
CRUNCHBASE_API_KEY=...

ALLOWED_ORIGINS=http://localhost:5173,https://agentsphere.vercel.app
CELERY_TASK_ALWAYS_EAGER=false
```

Required for normal local execution:

- `MONGODB_URI`
- `REDIS_URL`
- `CLERK_JWKS_URL` for authenticated API calls

Optional but recommended for full workflow results:

- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `SERPER_API_KEY`
- `CRUNCHBASE_API_KEY`
- `HUNTER_API_KEY`
- `APOLLO_API_KEY`

## Installation

From the backend directory:

```bash
cd /Users/pkarthikreddy/Documents/AgentForge/backend
python3.11 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
```

If `python3.11` is not available, use your Python 3.11 executable.

## Running The Backend

### Recommended API Command

Use this command to guarantee that the backend virtualenv is used:

```bash
cd /Users/pkarthikreddy/Documents/AgentForge/backend
./scripts/run_api.sh
```

The script prints the Python executable before starting Uvicorn.

Expected first line:

```text
Using Python: /Users/pkarthikreddy/Documents/AgentForge/backend/venv/bin/python
```

### Starting the Server

The application runs workflows asynchronously in-process — no separate worker process is needed!

```bash
cd /Users/pkarthikreddy/Documents/AgentForge/backend
./scripts/run_api.sh
```

Or run directly with your virtual environment:

```bash
cd /Users/pkarthikreddy/Documents/AgentForge/backend
./venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Health Check

Endpoint:

```http
GET /health
```

Command:

```bash
curl http://localhost:8000/health
```

Healthy response:

```json
{
  "status": "ok",
  "checks": {
    "app": "ok",
    "mongodb": "ok",
    "redis": "ok",
    "vector_store": {
      "provider": "pinecone"
    }
  }
}
```

Local fallback vector response:

```json
{
  "provider": "memory",
  "vector_count": 0
}
```

If MongoDB or Redis is down, the status becomes `degraded`.

## Authentication

Protected endpoints require:

```text
Authorization: Bearer <clerk_jwt_token>
```

The backend:

- Fetches Clerk JWKS from `CLERK_JWKS_URL`.
- Caches JWKS for 1 hour.
- Verifies token signature and expiry.
- Extracts `sub` as `user_id`.
- Extracts email and roles when present.

Test current user:

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <clerk_jwt_token>"
```

Expected response:

```json
{
  "user_id": "user_xxx",
  "email": "person@example.com",
  "roles": ["admin"]
}
```

## API Interface

FastAPI docs are available in development:

```text
http://localhost:8000/docs
```

Docs are disabled when `APP_ENV=production`.

### Workflow Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/workflows` | Create and start workflow |
| `GET` | `/api/v1/workflows` | List authenticated user's workflows |
| `GET` | `/api/v1/workflows/{workflow_id}` | Get workflow results and logs |
| `POST` | `/api/v1/workflows/{workflow_id}/approve` | Submit approval decisions |
| `DELETE` | `/api/v1/workflows/{workflow_id}` | Delete workflow data and vectors |

Create workflow request:

```json
{
  "name": "SaaS Funding Discovery",
  "icp": {
    "industry": ["B2B SaaS"],
    "headcount_min": 50,
    "headcount_max": 500,
    "funding_stages": ["Series A", "Series B"],
    "geography": ["United States"],
    "revenue_min_usd": 5000000,
    "tech_stack": ["Salesforce", "AWS"]
  },
  "personas": [
    {
      "name": "Economic Buyer",
      "titles": ["VP Sales", "CRO"],
      "priority": 1
    }
  ],
  "triggers": ["funding_round", "headcount_growth"]
}
```

Create workflow response:

```json
{
  "workflow_id": "wf_abc123",
  "status": "running",
  "websocket_url": "ws://localhost:8000/api/v1/ws/wf_abc123",
  "estimated_duration_seconds": 240
}
```

Workflow detail response shape:

```json
{
  "workflow": {
    "workflow_id": "wf_abc123",
    "name": "SaaS Funding Discovery",
    "status": "awaiting_approval",
    "summary_report": {}
  },
  "companies": [],
  "contacts": [],
  "summary_report": {},
  "logs": []
}
```

Approval request:

```json
{
  "decisions": [
    {
      "contact_id": "ct_abc123",
      "action": "approve"
    },
    {
      "contact_id": "ct_def456",
      "action": "reject",
      "reason": "Wrong persona"
    },
    {
      "contact_id": "ct_ghi789",
      "action": "edit",
      "edits": {
        "title": "CRO"
      }
    }
  ]
}
```

Approval response:

```json
{
  "workflow_id": "wf_abc123",
  "status": "completed",
  "processed": 3
}
```

### Agent Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/agents` | List agent registry |
| `GET` | `/api/v1/agents/{agent_id}` | Get one agent |
| `GET` | `/api/v1/agents/{agent_id}/logs` | Get logs for an agent |
| `PATCH` | `/api/v1/agents/{agent_id}` | Enable or disable agent |

Agent IDs:

- `planner_agent`
- `search_agent`
- `company_discovery_agent`
- `validation_agent`
- `decision_maker_agent`
- `contact_enrichment_agent`
- `summary_agent`
- `human_approval_agent`

Agent logs query:

```http
GET /api/v1/agents/search_agent/logs?workflow_id=wf_abc123&limit=50&offset=0
```

### Memory Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/memory/search` | Semantic company memory search |
| `GET` | `/api/v1/memory/stats` | Cache, vector, and document stats |
| `DELETE` | `/api/v1/memory/session/{session_id}` | Clear session memory |

Memory search:

```http
GET /api/v1/memory/search?q=series%20b%20saas&namespace=companies&top_k=5
```

Stats response shape:

```json
{
  "cache": {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "deletes": 0,
    "hit_rate": 0.0
  },
  "vector": {
    "provider": "memory",
    "vector_count": 0
  },
  "documents": {
    "workflows": 0,
    "companies": 0,
    "contacts": 0,
    "agent_logs": 0
  }
}
```

### WebSocket Endpoint

Connect to:

```text
ws://localhost:8000/api/v1/ws/{workflow_id}?token=<clerk_jwt_token>
```

Supported event types:

- `agent_started`
- `agent_completed`
- `progress`
- `result`
- `error`
- `approval_required`
- `workflow_completed`
- `log`

Example event:

```json
{
  "event": "agent_started",
  "workflow_id": "wf_abc123",
  "user_id": "user_xxx",
  "agent": "search_agent",
  "timestamp": "2026-06-28T10:01:00+00:00",
  "message": "search_agent started"
}
```

## Expected Results

With all API keys configured:

- Serper returns real news and web results.
- Crunchbase enriches company firmographics.
- Hunter returns email details.
- Apollo returns phone and LinkedIn enrichment.
- OpenAI creates planner and summary outputs.
- Pinecone stores persistent vector memory.
- Workflow should usually end in `awaiting_approval`.

With only MongoDB and Redis:

- API starts.
- Worker starts if dependencies are installed.
- Planner and Summary use fallback outputs.
- Pinecone uses local fallback memory.
- External enrichment may return empty values.
- Workflows can still be used for backend flow testing, but results may be sparse.

## Testing

Run tests with the backend virtualenv:

```bash
cd /Users/pkarthikreddy/Documents/AgentForge/backend
./venv/bin/python -m pytest
```

The tests cover:

- Planner output
- Search trigger detection
- ICP scoring formula
- Validation flow
- Redis cache helper behavior
- Vector duplicate fallback behavior
- Workflow router CRUD behavior
- Agent registry
- Workflow schema validation

## Troubleshooting

### `ModuleNotFoundError: No module named 'redis'`

Cause:

Uvicorn is running with global Python instead of `backend/venv`.

Fix:

```bash
cd /Users/pkarthikreddy/Documents/AgentForge/backend
./scripts/run_api.sh
```

Or:

```bash
cd /Users/pkarthikreddy/Documents/AgentForge/backend
./venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### `ModuleNotFoundError: No module named 'langchain_openai'`

The API no longer crashes at import time for missing `langchain-openai`. If you want OpenAI-backed planner, summary, and embeddings, install requirements into the backend venv:

```bash
cd /Users/pkarthikreddy/Documents/AgentForge/backend
./venv/bin/python -m pip install -r requirements.txt
```

### Health check is `degraded`

Check MongoDB and Redis. Both must be reachable for normal runtime.

Redis check:

```bash
redis-cli ping
```

MongoDB check depends on your local or cloud setup. Verify `MONGODB_URI`.

### Workflow stays `running`

Check:

- MongoDB is reachable.
- Server logs do not show an exception.
- `langgraph` is installed in the backend venv.

### WebSocket receives no events

Check:

- URL includes `?token=<clerk_jwt_token>`.
- Redis is running.
- Workflow ID is correct.

### Empty companies or contacts

Possible reasons:

- Missing Serper key.
- Search results did not match trigger patterns.
- ICP score below `0.65`.
- Duplicate company detected.
- Missing Crunchbase, Hunter, or Apollo keys.

## Docker

Build:

```bash
cd /Users/pkarthikreddy/Documents/AgentForge/backend
docker build -t agentsphere-backend .
```

Run:

```bash
docker run --env-file .env -p 8000:8000 agentsphere-backend
```

## Production Notes

Before production:

- Set `APP_ENV=production`.
- Use production MongoDB and Redis.
- Use production Clerk JWKS URL.
- Set all needed external API keys.
- Restrict `ALLOWED_ORIGINS`.
- Monitor API logs, Redis, MongoDB, and external API failures.
- Use persistent Pinecone for cross-run semantic memory.

When `APP_ENV=production`, FastAPI docs are disabled.
