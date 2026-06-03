# Lakshya - Getting Started Guide

A complete guide to setting up, running, and using every part of the platform from scratch.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Quick Start (5 minutes)](#3-quick-start-5-minutes)
4. [Detailed Setup Guide](#4-detailed-setup-guide)
   - [Step 1: Infrastructure (Docker)](#step-1-infrastructure-docker)
   - [Step 2: Environment Configuration](#step-2-environment-configuration)
   - [Step 3: Backend (Unified Server)](#step-3-backend-unified-server)
   - [Step 4: Frontend (React SPA)](#step-4-frontend-react-spa)
   - [Step 5: Database Seeding](#step-5-database-seeding)
5. [Verifying the Setup](#5-verifying-the-setup)
6. [Feature Guide](#6-feature-guide)
7. [API Reference](#7-api-reference)
8. [LLM Configuration](#8-llm-configuration)
9. [Database Management](#9-database-management)
10. [Troubleshooting](#10-troubleshooting)
11. [Project Structure](#11-project-structure)

---

## 1. Architecture Overview

```
                      +-------------------+
                      |  Frontend (React)  |
                      |   localhost:5173   |
                      +---------+---------+
                                |
                    +-----------v-----------+
                    |  Backend (Unified)    |
                    |   localhost:8001      |
                    |                       |
                    | LangGraph Agents      |
                    | FMP, FRED, NewsAPI    |
                    | NewsDataIO, Upstox   |
                    | Kite Connect          |
                    +-----------+-----------+
                                |
                 +--------------+--------------+
                 |              |              |
       +---------v---+ +-------v-----+ +------v------+
       | PostgreSQL  | |    Redis    | |   Qdrant    |
       | port 5432   | |  port 6379  | |  port 6333  |
       +-------------+ +-------------+ +-------------+
```

| Service | Port | Purpose |
|---------|------|---------|
| Frontend | 5173 | React SPA with demo/live data modes |
| Backend | 8001 | LangGraph agents, external data APIs, database, vector search, AI chat |
| PostgreSQL | 5432 | Primary database (companies, financials, users, portfolios) |
| Redis | 6379 | Caching and Celery task broker |
| Qdrant | 6333 | Vector database for semantic search over filings |

---

## 2. Prerequisites

| Tool | Version | Check Command | Install |
|------|---------|---------------|---------|
| Colima (macOS) | latest | `colima version` | `brew install colima` |
| Docker & Docker Compose | 20+ | `docker --version` | Comes with Colima |
| Python | 3.11+ | `python3 --version` | `brew install python@3.13` |
| Node.js | 18+ | `node --version` | `brew install node` |
| npm | 9+ | `npm --version` | Comes with Node |

**Required (at least one LLM provider):**

| Provider | Cost | Notes |
|----------|------|-------|
| Ollama | Free (local) | Default. Install from https://ollama.com |
| Groq | Free tier | Fast inference. https://console.groq.com |
| OpenAI | Paid | GPT-4o-mini or GPT-4o |
| DeepSeek | Paid | DeepSeek API |

**Optional API keys** (unlocks more data sources — app works without them using free fallbacks):
- FMP, Alpha Vantage, FRED, NewsAPI, NewsData.io, Upstox, Kite, OilPriceAPI, CommodityPriceAPI

---

## 3. Quick Start (5 minutes)

Run all of this from the project root:

```bash
# 0. Start Docker (macOS)
colima start

# 1. Start infrastructure
docker-compose up -d

# 2. Create Python virtual environment and install deps
python3 -m venv backend-ai/.venv
source backend-ai/.venv/bin/activate
pip install -r backend-ai/requirements.txt

# 3. Configure backend environment
cp backend-ai/.env.example backend-ai/.env
# Edit backend-ai/.env — set your DATABASE_URL and LLM provider (see Step 2)

# 4. Seed the database
cd backend-ai && python scripts/seed_db.py && cd ..

# 5. Seed causal intelligence data
cd backend-ai && python -m src.etl.seed_causal_data && cd ..

# 6. Start the backend (terminal 1)
cd backend-ai && python -m uvicorn src.main:app --port 8001 --reload

# 7. Start the frontend (terminal 2)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 in your browser.

---

## 4. Detailed Setup Guide

### Step 1: Infrastructure (Docker)

**macOS — start Colima first:**

```bash
colima start
```

Colima provides the Docker daemon on macOS. Without it, `docker` commands fail.

**Start PostgreSQL, Redis, and Qdrant:**

```bash
docker-compose up -d
```

> **Note:** Use `docker-compose` (with hyphen), not `docker compose`. The Colima Docker context may not support the plugin syntax.

Verify all containers are healthy:

```bash
docker-compose ps
```

Expected output:
```
NAME                   IMAGE                  STATUS         PORTS
lakshya-postgres-1   postgres:15-alpine     Up (healthy)   0.0.0.0:5432->5432/tcp
lakshya-redis-1      redis:7-alpine         Up (healthy)   0.0.0.0:6379->6379/tcp
lakshya-qdrant-1     qdrant/qdrant:latest   Up             0.0.0.0:6333->6333/tcp
```

**Port conflict — local postgres already running?**

Check if something is already on port 5432:

```bash
lsof -i :5432
```

If you see a local `postgres` process (not Docker), you have two options:

**Option A:** Stop the local postgres and use Docker's:
```bash
# Find and stop the local postgres process
brew services stop postgresql@15   # or whatever version
# Then restart Docker postgres
docker-compose restart postgres
```

**Option B:** Use your local postgres directly (skip Docker postgres):
- Make sure the user in your `.env` `DATABASE_URL` matches a role in your local postgres
- Create the database if it doesn't exist: `psql -c "CREATE DATABASE equity_research;"`
- Docker postgres port mapping will fail harmlessly — the other containers still work

**To stop infrastructure:**
```bash
docker-compose down          # stop containers (keeps data)
docker-compose down -v       # stop and DELETE all data
```

---

### Step 2: Environment Configuration

Copy the template:

```bash
cp backend-ai/.env.example backend-ai/.env
```

Edit `backend-ai/.env`:

#### Critical: DATABASE_URL

The `DATABASE_URL` user must match a role in your PostgreSQL instance.

**If using Docker postgres** (default user `postgres`):
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/equity_research
```

**If using local postgres** (check with `psql -c "\du"`):
```env
# Example if your local user is "ashutoshkumar"
DATABASE_URL=postgresql://ashutoshkumar@localhost:5432/equity_research
```

If your user doesn't exist yet, create it:
```bash
psql -c "CREATE ROLE your_username WITH LOGIN SUPERUSER CREATEDB;"
psql -c "CREATE DATABASE equity_research OWNER your_username;"
```

#### LLM Provider

Set **one** provider:

**Ollama (default, local, free):**
```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=deepseek-r1:8b
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768
```

Then pull the models:
```bash
ollama pull deepseek-r1:8b
ollama pull nomic-embed-text
```

**Groq (free tier, fast):**
```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

**OpenAI:**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your_key_here
OPENAI_MODEL=gpt-4o-mini
```

#### Frontend env

```bash
cp frontend/.env.example frontend/.env
```

This sets `VITE_BACKEND_URL=http://localhost:8001` — usually correct as-is.

---

### Step 3: Backend (Unified Server)

```bash
# From project root
python3 -m venv backend-ai/.venv
source backend-ai/.venv/bin/activate
pip install -r backend-ai/requirements.txt

cd backend-ai
python -m uvicorn src.main:app --port 8001 --reload
```

On startup, `init_db()` auto-creates all database tables.

**Verify:**
```bash
curl http://localhost:8001/health
# {"status":"healthy"}

curl http://localhost:8001/companies/
# {"total":4929,"companies":[...]}
```

**Swagger API docs:** http://localhost:8001/docs

---

### Step 4: Frontend (React SPA)

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Output:
```
VITE v6.4.2 ready in 566 ms
  Local:   http://localhost:5173/
```

**Open http://localhost:5173** in your browser.

The sidebar has a **Demo/Live** toggle — switch to **Live** to connect to the real backend.

---

### Step 5: Database Seeding

**Seed companies, financials, themes, and test user:**

```bash
source backend-ai/.venv/bin/activate
cd backend-ai
python scripts/seed_db.py
```

Output:
```
Seeded 20 companies, 5 ratio sets, 17 themes, 8 news articles
Test user ID: 00000000-0000-0000-0000-000000000001
Test user email: test@lakshya.dev
```

**Seed causal intelligence data:**

```bash
python -m src.etl.seed_causal_data
```

This populates:
- 11 causal chains (Oil -> Aviation, USD Strength -> IT Exports, etc.)
- 35 sector-exposure mappings
- 12 commodity price series

**What gets seeded:**
- 20 Indian companies: Reliance, TCS, HDFC Bank, Infosys, ICICI Bank, HUL, SBI, Airtel, ITC, L&T, Kotak, Axis, Wipro, HCL Tech, Sun Pharma, Maruti, Bajaj Finance, Asian Paints, Titan, Adani Enterprises
- Financial ratios for top 5 companies (ROE, ROCE, margins, P/E, etc.)
- 17 theme tags (AI, 5G, Green Energy, Infrastructure, Digital Banking, etc.)
- 8 news articles with sentiment labels
- 1 test user with a portfolio containing 8 holdings

---

## 5. Verifying the Setup

Run these checks to confirm everything is working:

```bash
# 1. Infrastructure
docker-compose ps                                    # all containers Up

# 2. Backend health
curl -s http://localhost:8001/health                  # {"status":"healthy"}

# 3. Database has data
curl -s http://localhost:8001/companies/ | python3 -c "import sys,json; print(json.load(sys.stdin)['total'], 'companies')"
# 20 companies (or 4929 if full universe synced)

# 4. Test user exists
curl -s "http://localhost:8001/portfolios/?user_id=00000000-0000-0000-0000-000000000001"

# 5. AI Chat (requires LLM provider configured)
curl -s -X POST http://localhost:8001/chat/query \
  -H "Content-Type: application/json" \
  -d '{"user_id":"00000000-0000-0000-0000-000000000001","query":"Analyze Reliance Industries","expertise_level":"intermediate"}'

# 6. Frontend
# Open http://localhost:5173, switch to Live mode
```

---

## 6. Feature Guide

### Lakshya Copilot (AI Research Copilot)

The core feature. An AI assistant that answers equity research questions using LangGraph agents.

1. Go to **Lakshya Copilot** in the sidebar
2. Ensure **Live** mode is active
3. Type a query and press Enter

**Example queries:**
```
"Analyze the financial health of Reliance Industries"
"Compare TCS vs Infosys on growth and profitability"
"Show my portfolio risk exposure"
"What is the latest news sentiment for HDFC Bank?"
```

### Company Analysis

View financial data, ratios, and AI-generated analysis for any company.

```bash
curl http://localhost:8001/companies/
curl http://localhost:8001/companies/{company_id}/financials
curl http://localhost:8001/companies/{company_id}/ratios
```

### Company Comparison

Compare 2-5 companies side by side.

```bash
curl -X POST http://localhost:8001/compare/ \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","company_ids":["ID1","ID2"],"query":"Compare on growth and valuation"}'
```

### Portfolio Management

```bash
curl "http://localhost:8001/portfolios/?user_id=USER_ID"
curl http://localhost:8001/portfolios/{portfolio_id}
```

### Document Upload

Upload PDFs/PPTs for AI analysis via RAG:

```bash
curl -X POST http://localhost:8001/chat/upload \
  -F "file=@annual_report.pdf" \
  -F "user_id=USER_ID"
```

### Screening & Discovery

```bash
curl -X POST http://localhost:8001/screens/run \
  -H "Content-Type: application/json" \
  -d '{"sector":"Information Technology","min_market_cap":200000}'
```

---

## 7. API Reference

All APIs on port 8001. Interactive docs at http://localhost:8001/docs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/chat/query` | AI research query |
| POST | `/chat/upload` | Upload document |
| GET | `/companies/` | List companies |
| GET | `/companies/{id}` | Company details |
| GET | `/companies/{id}/financials` | Financial statements |
| GET | `/companies/{id}/ratios` | Financial ratios |
| POST | `/compare/` | Compare companies |
| GET/POST | `/portfolios/` | Portfolio CRUD |
| POST | `/portfolios/{id}/holdings` | Add holding |
| GET/POST | `/alerts/` | Alert rules |
| GET/POST | `/watchlists/` | Watchlists |
| GET | `/timeline/` | Aggregated feed |
| POST | `/screens/run` | Execute screen |

---

## 8. LLM Configuration

| Provider | `LLM_PROVIDER` | Default Model | Notes |
|----------|----------------|---------------|-------|
| Ollama | `ollama` | `deepseek-r1:8b` | Local, free, default |
| Groq | `groq` | `openai/gpt-oss-20b` | Free tier, fast |
| OpenAI | `openai` | `gpt-4o-mini` | Best quality, paid |
| DeepSeek | `deepseek` | `deepseek-chat` | Alternative API |

Switch providers by editing `backend-ai/.env` and restarting the backend.

---

## 9. Database Management

### View tables

```bash
psql -d equity_research -c "\dt"
psql -d equity_research -c "SELECT count(*) FROM companies;"
```

### Reset database

```bash
psql -c "DROP DATABASE equity_research;"
psql -c "CREATE DATABASE equity_research;"
# Grant access if needed:
psql -c "GRANT ALL PRIVILEGES ON DATABASE equity_research TO your_user;"
cd backend-ai && python scripts/seed_db.py
python -m src.etl.seed_causal_data
```

### Run Alembic migrations

```bash
cd backend-ai
alembic revision --autogenerate -m "describe changes"
alembic upgrade head
alembic current
```

---

## 10. Troubleshooting

### "failed to fetch" in frontend
- Backend is probably not running or crashing. Check: `curl http://localhost:8001/health`
- Check backend logs for errors
- Ensure you're in **Live** mode, not Demo

### "role XXX does not exist" on database connection
- Your `DATABASE_URL` user doesn't exist in PostgreSQL
- Fix: `psql -c "CREATE ROLE your_user WITH LOGIN SUPERUSER CREATEDB;"`
- Or update `.env` to match an existing role: `psql -c "\du"`

### Port 5432 already in use (Docker postgres won't start)
- A local postgres is already running on that port
- Either stop it (`brew services stop postgresql@15`) or use the local postgres directly
- See [Step 1](#step-1-infrastructure-docker) for details

### "docker compose" command fails on macOS
- Use `docker-compose` (with hyphen) instead
- Or ensure Colima is running: `colima start`

### Backend starts but /companies returns empty
- Database hasn't been seeded: `python backend-ai/scripts/seed_db.py`
- Or the database is empty because `init_db()` created fresh tables

### psycopg2 build fails during pip install
- macOS: `brew install postgresql` (provides `pg_config`)
- Or use Python 3.11/3.12 which have pre-built wheels

### Ollama not responding
- Start it: `ollama serve`
- Pull models: `ollama pull deepseek-r1:8b && ollama pull nomic-embed-text`
- Verify: `curl http://localhost:11434/api/tags`

### Port 8001 already in use
- Kill it: `pkill -f "uvicorn src.main:app"`
- Or use a different port: `python -m uvicorn src.main:app --port 8002`

### Backend restarts after .env change
```bash
pkill -f "uvicorn src.main:app"
cd backend-ai && python -m uvicorn src.main:app --port 8001 --reload
```

---

## 11. Project Structure

```
lakshya/
├── backend-ai/               # Unified backend server (port 8001)
│   ├── alembic/              #   Database migrations
│   ├── src/
│   │   ├── app/              #   FastAPI factory/middleware/routers/lifespan
│   │   ├── domains/          #   Domain routes + services
│   │   ├── services/         #   Shared business services
│   │   ├── integrations/     #   Market data provider ownership
│   │   ├── agents/           #   Deep orchestrator + sub-agents + tools
│   │   ├── etl/              #   Data ingestion, seed scripts
│   │   ├── llm/              #   LLM/embedding factory
│   │   ├── db/               #   Database session + SQLAlchemy models
│   │   ├── config.py         #   Pydantic settings (reads .env)
│   │   └── main.py           #   FastAPI entry point
│   ├── scripts/              #   Operational scripts
│   │   ├── seed_db.py        #   Seed companies, users, portfolios
│   │   ├── run_agent.py      #   CLI agent runner
│   │   └── debug_run.py      #   Debug helpers
│   ├── .env.example          #   Environment template
│   ├── .env                  #   Your local config (git-ignored)
│   ├── requirements.txt      #   Python dependencies
│   └── alembic.ini           #   Alembic config
│
├── frontend/                 # React SPA (port 5173)
│   ├── src/
│   │   ├── shared/           #   Shared API, types, UI components
│   │   ├── features/         #   Feature modules (chat, compare, etc.)
│   │   ├── components/       #   Layout, sidebar, app shell
│   │   ├── App.tsx           #   Root component
│   │   └── main.tsx          #   Entry point
│   ├── .env.example          #   VITE_BACKEND_URL
│   ├── .env                  #   Your local config
│   └── package.json
│
├── docker-compose.yml        # PostgreSQL, Redis, Qdrant
├── plans/                    # Architecture docs
├── docs/                     # Additional documentation
└── GETTING_STARTED.md        # This file
```

---

## macOS-Specific Notes

If you're on macOS and hit issues, the usual suspects are:

1. **Colima not running** — `colima start` before any docker command
2. **Local postgres conflicting with Docker** — check `lsof -i :5432`
3. **`docker compose` vs `docker-compose`** — use the hyphenated version with Colima
4. **psycopg2 won't install** — `brew install postgresql` for `pg_config`
5. **Port already in use** — `lsof -i :PORT` then `kill PID`
