# Agent Architecture

The backend-ai chat system is a **native LangGraph hybrid supervisor**: a router
classifies each query and sends it down either a fast deterministic workflow or an
agentic specialist loop. Both paths share one grounded synthesis step, stream
tokens over SSE, and persist to Postgres.

> Historical note: an earlier `deepagents` orchestrator + subagents design was
> built but never used in the live path; it was removed in favour of the graph
> below. There is no more `orchestrator.py` / `subagents/`.

## High-level flow

```
                              ┌─ simple  → plan → gather (parallel) → synthesize
POST /chat/query[/stream] →  router  ─┤
                              └─ complex → agent (ReAct loop) ──────→ synthesize
```

- **router** — one LLM call classifies the query `simple` vs `complex`
  (keyword fallback). Simple = a direct lookup; complex = multi-step reasoning,
  judgement, or several domains (recommendations, rebalancing, comparisons with a
  verdict, open-ended strategy).
- **Simple path (workflow):** `plan` picks evidence tasks → `gather` runs them in
  parallel via the **Send API** → `synthesize` writes the answer. ~2 LLM calls.
- **Complex path (agent):** a bounded ReAct loop (≤4 steps) where the LLM
  dynamically calls **specialist tools**, using each result to decide the next,
  then hands the gathered evidence to `synthesize`.
- **synthesize** (shared) — streams the grounded answer; only this node's tokens
  are surfaced to the client.

## Core modules

| Concern | File |
|---|---|
| The graph (router / plan / gather / agent / synthesize) | `src/agents/graph.py` |
| 7 specialist tools | `src/agents/specialists.py` |
| Evidence tools reused by `plan`/`gather` (planner, worker, aggregator) | `src/domains/chat/research_pipeline.py` |
| Grounded domain tools | `src/agents/tools/` |
| Guardrails (input, injection, rate-limit, output grounding) | `src/agents/guardrails.py` |
| Postgres checkpointer + store | `src/agents/memory.py` |
| API entrypoint | `src/domains/chat/routes.py` → `service.py` |

## The 7 specialist agents

Exposed as tools the complex-path agent can call by name (`SPECIALIST_TOOLS`):

| Specialist | Purpose |
|---|---|
| `company_analysis` | Single-company deep dive: financials, ratios, risk flags |
| `news_analysis` | Recent news + sentiment for a company |
| `compare_companies` | Side-by-side peer comparison |
| `document_analysis` | Search a company's filings/annual reports (Qdrant) |
| `thematic_discovery` | Find companies matching a macro/sector theme |
| `causal_analysis` | Hidden-risk / causal chains (commodity → sector → stock), DB-grounded |
| `portfolio_analysis` | The user's holdings, risk metrics, causal exposure |

Company-scoped specialists resolve names → IDs internally; `portfolio_analysis`
reads the active user from the injected run `config` (the LLM never sees UUIDs).

## Streaming

The graph is streamed with `stream_mode=["custom", "messages"]`:

- **custom** (`get_stream_writer`) → SSE `stage` events: `routing`, `planning`,
  `evidence`, `specialist`, `reasoning`, `synthesizing`.
- **messages**, filtered to the `synthesize` node → SSE `token` events.
- The service (`ChatService.stream_query`) maps these to `stage` / `token` /
  `done` / `error` SSE events; dashboard suggestions stream via `stream_prompt`.

## Memory

`src/agents/memory.py` shares one psycopg3 pool between:

- **PostgresSaver** checkpointer — conversation continuity keyed by
  `thread_id = session_id`; survives restarts and is shared across workers.
- **PostgresStore** — long-term `/memories/`.

Both fall back to in-memory if Postgres is unavailable.

## Grounding & guardrails

- Causal reasoning is constrained to sectors/commodities proven in the
  `SectorExposure` graph, which is verified against 2-year price correlations
  (`verified_confidence`, `market_agreement`).
- Guardrails run in the service around the graph: rate-limit + prompt-injection
  on input; grounding + disclaimer on output. The synthesis prompt forbids
  echoing raw tool JSON and requires a self-verification pass.

## Notes

- Tech: LangGraph `StateGraph` + Send API, `langgraph-checkpoint-postgres`,
  Qdrant (doc vectors), Ollama embeddings, NVIDIA NIM `gpt-oss-120b` LLM.
- If the architecture changes again, update this file in the same PR to avoid drift.
