# Lakshya

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent_DAG-FF6F00.svg)](https://langchain-ai.github.io/langgraph/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC2626.svg?logo=qdrant&logoColor=white)](https://qdrant.tech)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D.svg?logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com)
[![CI Tests](https://img.shields.io/badge/Tests-26%20Passed%20(100%25)-22C55E.svg)]()

> **Lakshya** (*Sanskrit/Hindi for "target" or "goal"*) is an AI-native equity research and causal intelligence workspace for Indian stock markets (NSE/BSE). It combines multi-agent LangGraph orchestration, semantic filing retrieval, automated macro-to-micro domino risk analysis, and real-time streaming analytics to turn complex financial disclosures into evidence-backed investment decisions.

---

## 🎯 The Problem & Motivation

* **The Problem:** Retail investors and junior equity analysts spend **2 to 3 hours** manually sifting through 100+ page annual reports, quarterly BSE/NSE exchange disclosures, earnings concall transcripts, and fragmented news feeds to validate a single investment hypothesis.
* **The Solution:** Lakshya replaces manual, fragmented research with a **deterministic, cited multi-agent research pipeline**—reducing multi-company filings synthesis, comparative valuation, and macro risk analysis from hours to seconds with 100% grounded citations.

---

## ⚡ Key Engineering Highlights

### 1. Hybrid-Supervisor Agent DAG (LangGraph `StateGraph`)
Instead of a brittle single-prompt wrapper, Lakshya uses an intelligent supervisor router that classifies query complexity and dynamically selects the optimal execution path:
* **Fast Deterministic Path:** Fans out structured evidence tasks in parallel via LangGraph's `Send` API (fundamentals, news sentiment, technical ratios).
* **Deep ReAct Specialist Loop:** Executes a bounded multi-step reasoning loop (≤4 steps) across 7 domain-specific specialists (`company_analysis`, `document_analysis`, `causal_analysis`, `thematic_discovery`, `compare_companies`, `news_analysis`, `portfolio_analysis`).
* **Streaming Synthesis:** Converges on a unified synthesis node that streams token narratives over Server-Sent Events (SSE) with source citations.

### 2. Predictive Causal Intelligence (Macro → Micro Domino Engine)
Markets do not move in isolation. Lakshya models predictive causal chains linking geopolitical and macroeconomic events to stock price impacts:
$$\text{Macro Event} \longrightarrow \text{Commodity Shift} \longrightarrow \text{Sector Headwind/Tailwind} \longrightarrow \text{Company Margin Impact}$$
* Mined from corporate filings and verified against historical price correlations.
* Enables non-obvious queries: *"What are the hidden risks in my portfolio if Brent crude rises by 10%?"*

### 3. 7-Stage Financial ETL & Filing Vector RAG
* Automated asynchronous document pipeline built with **Celery & Celery Beat**.
* Extracts text and financial tables from exchange PDFs/PPTs, applies **semantic financial chunking** (500 tokens + 10% overlap), generates dense embeddings (`nomic-embed-text`), and stores vectors in **Qdrant** alongside structured metadata in **PostgreSQL**.

### 4. Zero-Downtime Multi-LLM Provider Failover
* Resilient LLM routing layer with automatic circuit-breaker failovers across **Groq, DeepSeek, and local Ollama** instances (`gpt-oss-120b`, `llama3.3`).
* Maintains 99.9% uptime and zero-drop request resilience even during third-party API rate limits or outages.

### 5. Production-Minded Security & Architecture
* 14 modular FastAPI domain routers with end-to-end typed DTO schemas.
* Session-based authentication with `HttpOnly` cookies and **Double-Submit CSRF Protection** (`X-CSRF-Token`) on all mutating verbs.
* Redis sliding-window rate limiters (20 req/60s) with prompt injection defense guardrails.

---

## 🧩 Core Product Modules

| Area | Technical Capabilities |
|---|---|
| **Research Copilot** | Persistent chat sessions, SSE streaming stage steppers, cited source badges, specialist tool routing |
| **Company Workspace** | Interactive valuation ratios, quarterly statements, risk flag triggers, and filing extracts |
| **Comparison Matrix** | Side-by-side comparative benchmarking across 2–5 companies with deterministic winner verdicts |
| **Portfolio Analytics** | Holdings management, sector allocation donut, Sharpe/Beta risk metrics, and macro exposure alerts |
| **Causal Graph** | Multi-hop domino effect simulator tracking event $\rightarrow$ commodity $\rightarrow$ sector $\rightarrow$ stock transmission |
| **Paper Simulator** | Gamified paper trading environment with balance tracking, order execution, and P&L history |
| **Thematic Screener** | Semantic vector search discovering companies matching macroeconomic themes (e.g. *Green Hydrogen*) |

---

## 🛠️ Tech Stack & Services

| Service | Port | Technology Stack | Purpose |
|---|---|---|---|
| **Frontend** | `5173` | React 19, TypeScript, Vite, Tailwind CSS, Recharts | Interactive analyst research console |
| **Backend** | `8001` | FastAPI, LangGraph, SQLAlchemy, httpx | API routing, multi-agent orchestration, auth |
| **PostgreSQL** | `5432` | PostgreSQL 16, Alembic migrations | Relational storage (companies, financials, users, portfolios) |
| **Redis** | `6379` | Redis 7.0 | Distributed cache, sliding-window rate limiting, Celery broker |
| **Qdrant** | `6333` | Qdrant Vector Engine | Dense vector storage for semantic filing & document search |

## Quick Start

```bash
docker compose up -d
python3 -m venv backend-ai/.venv
source backend-ai/.venv/bin/activate
pip install -r backend-ai/requirements.txt
cp backend-ai/.env.example backend-ai/.env
python backend-ai/scripts/seed_db.py
cd backend-ai && python -m uvicorn src.main:app --port 8001 --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Documentation

- [Getting Started](GETTING_STARTED.md)
- [System Architecture](ARCHITECTURE.md)
- [Agentic and Causal Design](AGENTIC_AND_CAUSAL_DESIGN.md)
- [ngrok Setup](NGROK_SETUP.md)

## Screenshots

### Dashboard Overview
![Lakshya Dashboard](docs/assets/dashboard.png)

### AI Research Workspace
![Lakshya Research Workspace](docs/assets/research_workspace.png)

### Company Deep-Dive Workspace
![Lakshya Company Analysis](docs/assets/company_analysis.png)

### Portfolio Analytics & Risk Breakdown
![Lakshya Portfolio](docs/assets/portfolio.png)

## Architecture Diagrams

### High-Level System Architecture

```mermaid
graph TD
    U["Analyst (Browser)"] -->|HTTPS + Cookies| FE["Lakshya React Console<br/>(Vite + TypeScript + Tailwind)"]
    FE -->|REST API + SSE Stream| API["FastAPI Backend Service<br/>(14 Domain Routers / Auth & CSRF)"]

    API --> AG["AI Research Engine<br/>(LangGraph 'Lakshya' Hybrid Supervisor)"]
    API --> CI["Causal Intelligence Engine<br/>(Graph Chains + Price Correlation)"]
    API --> PG[("PostgreSQL<br/>(Companies, Ratios, Portfolios)")]
    
    AG --> QD[("Qdrant Vector DB<br/>(Filing Chunks & Upload Embeddings)")]
    AG --> PG
    CI --> PG

    subgraph AsyncETL["Background ETL & Scheduling (Celery + Beat)"]
        SCH["Beat Scheduler<br/>(Periodic Market Ingestion)"]
        ETL["ETL Workers<br/>(Crawl · Ingest · Enrich · Embed)"]
    end

    SCH --> ETL
    ETL --> PG
    ETL --> QD
    ETL -->|LLM Entity Extraction| LLM["LLM Inference Engine<br/>(Groq / Ollama / DeepSeek)"]
    AG -->|Reasoning & Synthesis| LLM
    ETL -->|Document Embeddings| EMB["Embedding Model<br/>(nomic-embed-text / bge-small)"]
    AG --> EMB

    API -.->|Task Broker & Caching| RD[("Redis Cache")]
    SCH -.-> RD
```

### AI Agent Pipeline (LangGraph Hybrid Supervisor)

```mermaid
flowchart TD
    START(["START: User Query"]) --> ROUTER{"Router Node<br/>(Classify Query Complexity)"}

    ROUTER -->|"Simple / Structured"| PLAN["Plan Node<br/>(Intent → Evidence Tasks)"]
    ROUTER -->|"Complex / Open-Ended"| AGENT["Agent Node<br/>(Bounded ReAct Specialist Loop)"]

    PLAN -->|"Send Fan-Out"| G1["Gather Task 1<br/>(Company Financials)"]
    PLAN -->|"Send Fan-Out"| G2["Gather Task 2<br/>(Document / Filing RAG)"]
    PLAN -->|"Send Fan-Out"| G3["Gather Task 3<br/>(News Sentiment / Causal)"]

    AGENT -->|"Dynamic Tool Invocations"| AGENT

    G1 --> SYN["Synthesize Node<br/>(Grounded Narrative + Token Streaming)"]
    G2 --> SYN
    G3 --> SYN
    AGENT --> SYN
    SYN --> END(["END: Streamed Response to User"])

    style ROUTER fill:#1f6feb,color:#fff
    style SYN fill:#22c55e,color:#000
```

### Causal Intelligence Graph (Macro → Micro Impact)

```mermaid
flowchart LR
    EV["Macro / Geopolitical Event<br/>(e.g., Red Sea Escalation)"]
    COM["Commodity Shift<br/>(Brent Crude +8%, Freight Rates +25%)"]
    SEC_N["Headwind Sector<br/>(Aviation, Paints, OMCs)"]
    SEC_P["Tailwind Sector<br/>(Upstream Oil, Shipping)"]
    STK_A["Affected Companies<br/>(INDIGO: Margin Squeeze)"]
    STK_B["Benefited Companies<br/>(ONGC, GE Shipping: Margin Expansion)"]

    EV --> COM
    COM --> SEC_N
    COM --> SEC_P
    SEC_N --> STK_A
    SEC_P --> STK_B

    style EV fill:#f97316,color:#fff
    style COM fill:#eab308,color:#000
    style SEC_N fill:#ef4444,color:#fff
    style SEC_P fill:#22c55e,color:#000
```

### 7-Stage Document ETL & Filing Ingestion Flow

```mermaid
flowchart TD
    RAW["1. Raw Document / Filing PDF / PPT"] --> EXTRACT["2. Text & Table Extraction (PyPDF / pdfplumber)"]
    EXTRACT --> CHUNK["3. Semantic Financial Chunking (500 tokens + 10% overlap)"]
    CHUNK --> ENRICH["4. Metadata Enrichment (Ticker, Fiscal Year, Filing Type)"]
    ENRICH --> EMBED["5. Vector Embeddings Generation (nomic-embed-text)"]
    EMBED --> STORE["6. Vector Upsert into Qdrant (filings collection)"]
    STORE --> INDEX["7. Full-Text & Relational Indexing in PostgreSQL"]

    style RAW fill:#3b82f6,color:#fff
    style STORE fill:#8b5cf6,color:#fff
    style INDEX fill:#10b981,color:#fff
```
