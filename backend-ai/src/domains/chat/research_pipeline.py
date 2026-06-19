"""Planner-driven chat research pipeline.

The pipeline breaks a query into task units, executes them in parallel, and
hands the consolidated evidence to the existing LLM layer for final synthesis.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Literal, Optional
from uuid import UUID

from src.agents.tools.causal_tools import (
    analyze_causal_chain_with_llm,
    get_market_hidden_patterns,
    get_portfolio_causal_analysis,
)
from src.agents.tools.financial import calculate_ratios, detect_risk_flags, get_latest_financials
from src.agents.tools.news import get_recent_news
from src.agents.tools.portfolio import calculate_portfolio_metrics, get_portfolio_holdings
from src.agents.tools.vector_search import search_filings, search_user_upload, thematic_discovery_search
from src.agents.tools.web_search import internet_search
from src.db.database import get_db
from src.db.models import Company
from src.config import get_settings

logger = logging.getLogger(__name__)

TaskKind = Literal[
    "company_snapshot",
    "news_snapshot",
    "filings_snapshot",
    "portfolio_snapshot",
    "thematic_snapshot",
    "causal_snapshot",
    "web_snapshot",
]


@dataclass(frozen=True)
class PlannedTask:
    """A unit of work that can run in the worker pool."""

    name: str
    kind: TaskKind
    params: dict[str, Any]


@dataclass(frozen=True)
class TaskResult:
    """Normalized worker output for the aggregator."""

    name: str
    kind: TaskKind
    payload: Any
    source: dict[str, Any]


class ResearchPlanner:
    """Convert a chat request into a bounded task plan.

    Intent detection uses a fast LLM classifier when available and falls back to
    keyword heuristics on any failure. ID-driven tasks (company / upload) are
    added deterministically regardless of intent, since they depend on request
    context rather than phrasing.
    """

    # Intents the classifier may return. ``causal`` routes to the Causal
    # Detective, which was previously unreachable from the chat pipeline.
    _INTENTS = ("news", "filings", "portfolio", "thematic", "causal", "web")

    _KEYWORDS = {
        "news": ("news", "sentiment", "headline", "quarter", "annual report", "latest"),
        "filings": ("filing", "10-k", "annual report", "disclosure", "prospectus"),
        "portfolio": ("portfolio", "holdings", "exposure", "allocation", "my stocks"),
        "thematic": ("theme", "sector", "industry", "related companies", "similar companies"),
        "causal": (
            "causal", "hidden", "domino", "ripple", "knock-on", "second-order",
            "second order", "not obvious", "what's not", "supply chain",
            "commodity impact", "downstream", "cascade", "affected by",
        ),
    }

    def plan(
        self,
        query: str,
        user_id: UUID,
        company_id: Optional[UUID],
        upload_id: Optional[UUID],
        primary_portfolio_id: Optional[UUID],
    ) -> list[PlannedTask]:
        tasks: list[PlannedTask] = []

        # ── ID-driven deterministic tasks ─────────────────────────────────
        if company_id:
            tasks.append(PlannedTask("company_snapshot", "company_snapshot", {"company_id": str(company_id)}))
        if upload_id:
            tasks.append(
                PlannedTask(
                    "filings_snapshot",
                    "filings_snapshot",
                    {"upload_id": str(upload_id), "user_id": str(user_id), "query": query},
                )
            )
        elif company_id:
            tasks.append(
                PlannedTask("filings_snapshot", "filings_snapshot", {"company_id": str(company_id), "query": query})
            )

        # ── Intent-driven tasks ───────────────────────────────────────────
        intents = self._detect_intents(query)

        if "news" in intents and company_id:
            tasks.append(PlannedTask("news_snapshot", "news_snapshot", {"company_id": str(company_id)}))
        if "portfolio" in intents and primary_portfolio_id:
            tasks.append(
                PlannedTask("portfolio_snapshot", "portfolio_snapshot", {"portfolio_id": str(primary_portfolio_id)})
            )
        if "thematic" in intents and not company_id:
            tasks.append(PlannedTask("thematic_snapshot", "thematic_snapshot", {"query": query}))
        if "causal" in intents:
            params: dict[str, Any] = {"query": query}
            if primary_portfolio_id:
                params["portfolio_id"] = str(primary_portfolio_id)
            tasks.append(PlannedTask("causal_snapshot", "causal_snapshot", params))

        if not tasks:
            tasks.append(PlannedTask("web_snapshot", "web_snapshot", {"query": query}))

        return self._dedupe(tasks)

    def _detect_intents(self, query: str) -> set[str]:
        """Return the set of intents for a query (LLM first, keyword fallback)."""
        llm_intents = self._llm_intents(query)
        if llm_intents is not None:
            return llm_intents
        return self._keyword_intents(query)

    def _keyword_intents(self, query: str) -> set[str]:
        query_lower = query.lower()
        return {
            intent
            for intent, keywords in self._KEYWORDS.items()
            if any(k in query_lower for k in keywords)
        }

    def _llm_intents(self, query: str) -> Optional[set[str]]:
        """Classify a query into intents with one cached LLM call.

        Returns ``None`` on any failure so the caller falls back to keywords.
        """
        from src.utils.cache import get_analysis_cache

        cache = get_analysis_cache()
        cache_key = cache.make_key("intent_v1", query.strip().lower())
        cached = cache.get(cache_key)
        if cached is not None:
            return set(cached)

        prompt = (
            "Classify this equity-research query into zero or more intents. "
            "Return ONLY a JSON array of strings from this exact set: "
            '["news","filings","portfolio","thematic","causal","web"].\n'
            "- news: recent news/sentiment/results for a company\n"
            "- filings: content inside regulatory filings/annual reports\n"
            "- portfolio: the user's own holdings, exposure, or allocation\n"
            "- thematic: sector/industry/theme or finding similar companies\n"
            "- causal: hidden/second-order/domino effects, commodity or supply-chain impacts\n"
            "- web: general knowledge needing a web search\n"
            f"\nQuery: {query}\nJSON:"
        )
        try:
            from src.llm import get_llm
            from langchain_core.messages import HumanMessage

            resp = get_llm(temperature=0.0).invoke([HumanMessage(content=prompt)])
            content = resp.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1].lstrip("json").strip()
            parsed = json.loads(content)
            intents = {i for i in parsed if i in self._INTENTS}
            cache.set(cache_key, sorted(intents))
            return intents
        except Exception as e:
            logger.warning("LLM intent classification failed, using keywords: %s", e)
            return None

    @staticmethod
    def _dedupe(tasks: list[PlannedTask]) -> list[PlannedTask]:
        seen: set[TaskKind] = set()
        ordered: list[PlannedTask] = []
        for task in tasks:
            if task.kind in seen:
                continue
            seen.add(task.kind)
            ordered.append(task)
        return ordered


class ResearchWorkerPool:
    """Execute planned tasks with bounded parallelism."""

    def __init__(self, max_workers: int) -> None:
        self.max_workers = max(1, max_workers)

    def run(self, tasks: list[PlannedTask]) -> list[TaskResult]:
        if not tasks:
            return []

        results: list[TaskResult] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(tasks))) as executor:
            future_map = {executor.submit(self._execute_task, task): task for task in tasks}
            for future in as_completed(future_map):
                task = future_map[future]
                try:
                    results.append(future.result())
                except Exception as exc:  # pragma: no cover - defensive guard
                    logger.exception("Worker task failed: %s", task.name)
                    results.append(
                        TaskResult(
                            name=task.name,
                            kind=task.kind,
                            payload={"error": str(exc)},
                            source={"name": task.name, "kind": task.kind, "status": "error"},
                        )
                    )

        kind_order = {task.kind: index for index, task in enumerate(tasks)}
        return sorted(results, key=lambda item: kind_order.get(item.kind, 0))

    def _execute_task(self, task: PlannedTask) -> TaskResult:
        if task.kind == "company_snapshot":
            return self._run_company_snapshot(task)
        if task.kind == "news_snapshot":
            return self._run_news_snapshot(task)
        if task.kind == "filings_snapshot":
            return self._run_filings_snapshot(task)
        if task.kind == "portfolio_snapshot":
            return self._run_portfolio_snapshot(task)
        if task.kind == "thematic_snapshot":
            return self._run_thematic_snapshot(task)
        if task.kind == "causal_snapshot":
            return self._run_causal_snapshot(task)
        return self._run_web_snapshot(task)

    @staticmethod
    def _tool_output(tool: Any, payload: dict[str, Any]) -> Any:
        return tool.invoke(payload)

    def _run_company_snapshot(self, task: PlannedTask) -> TaskResult:
        company_id = task.params["company_id"]
        company = self._load_company(company_id)
        financials = self._tool_output(get_latest_financials, {"company_id": company_id, "periods": 4})
        ratios = self._tool_output(calculate_ratios, {"company_id": company_id})
        risk_flags = self._tool_output(detect_risk_flags, {"company_id": company_id})
        from src.agents.tools.financial import fetch_company_insights

        try:
            document_insights = fetch_company_insights(company_id)
        except Exception:
            document_insights = []
        payload = {
            "company": company,
            "financials": financials,
            "ratios": ratios,
            "risk_flags": risk_flags,
            "document_insights": document_insights,
        }
        return TaskResult(
            name=task.name,
            kind=task.kind,
            payload=payload,
            source={"name": task.name, "kind": task.kind, "company_id": company_id, "status": "ok"},
        )

    def _run_news_snapshot(self, task: PlannedTask) -> TaskResult:
        company_id = task.params["company_id"]
        payload = self._tool_output(get_recent_news, {"company_id": company_id, "days": 30, "limit": 8})
        return TaskResult(
            name=task.name,
            kind=task.kind,
            payload=payload,
            source={"name": task.name, "kind": task.kind, "company_id": company_id, "status": "ok"},
        )

    def _run_filings_snapshot(self, task: PlannedTask) -> TaskResult:
        if "upload_id" in task.params:
            payload = self._tool_output(
                search_user_upload,
                {
                    "user_id": task.params["user_id"],
                    "upload_id": task.params["upload_id"],
                    "query": task.params["query"],
                    "limit": 8,
                },
            )
            source = {"name": task.name, "kind": task.kind, "upload_id": task.params["upload_id"], "status": "ok"}
        else:
            company_id = task.params["company_id"]
            payload = self._tool_output(
                search_filings,
                {
                    "company_id": company_id,
                    "query": task.params["query"],
                    "limit": 8,
                },
            )
            source = {"name": task.name, "kind": task.kind, "company_id": company_id, "status": "ok"}
        return TaskResult(name=task.name, kind=task.kind, payload=payload, source=source)

    @staticmethod
    def _load_company(company_id: str) -> dict[str, Any]:
        db = next(get_db())
        try:
            company = db.query(Company).filter(Company.id == UUID(company_id)).first()
            if not company:
                return {"error": f"Company not found for id {company_id}"}
            return {
                "company_id": str(company.id),
                "name": company.name,
                "ticker_nse": company.ticker_nse,
                "ticker_bse": company.ticker_bse,
                "sector": company.sector,
                "industry": company.industry,
            }
        finally:
            db.close()

    def _run_portfolio_snapshot(self, task: PlannedTask) -> TaskResult:
        portfolio_id = task.params["portfolio_id"]
        holdings = self._tool_output(get_portfolio_holdings, {"portfolio_id": portfolio_id})
        metrics = self._tool_output(calculate_portfolio_metrics, {"portfolio_id": portfolio_id})
        payload = {"holdings": holdings, "metrics": metrics}
        return TaskResult(
            name=task.name,
            kind=task.kind,
            payload=payload,
            source={"name": task.name, "kind": task.kind, "portfolio_id": portfolio_id, "status": "ok"},
        )

    def _run_thematic_snapshot(self, task: PlannedTask) -> TaskResult:
        payload = self._tool_output(thematic_discovery_search, {"query": task.params["query"], "limit": 10})
        return TaskResult(
            name=task.name,
            kind=task.kind,
            payload=payload,
            source={"name": task.name, "kind": task.kind, "status": "ok"},
        )

    def _run_causal_snapshot(self, task: PlannedTask) -> TaskResult:
        """Gather causal intelligence: market-wide hidden patterns, an LLM causal
        chain for the query trigger, and portfolio exposures when available.

        Causal tools are plain functions (not LangChain tools), so they are
        called directly rather than via ``_tool_output``.
        """
        query = task.params["query"]
        portfolio_id = task.params.get("portfolio_id")
        payload: dict[str, Any] = {
            "hidden_patterns": get_market_hidden_patterns(),
            "causal_chain": analyze_causal_chain_with_llm(query),
        }
        if portfolio_id:
            payload["portfolio_causal"] = get_portfolio_causal_analysis(portfolio_id)
        return TaskResult(
            name=task.name,
            kind=task.kind,
            payload=payload,
            source={"name": task.name, "kind": task.kind, "status": "ok"},
        )

    def _run_web_snapshot(self, task: PlannedTask) -> TaskResult:
        payload = self._tool_output(internet_search, {"query": task.params["query"]})
        return TaskResult(
            name=task.name,
            kind=task.kind,
            payload=payload,
            source={"name": task.name, "kind": task.kind, "status": "ok"},
        )


class ResultAggregator:
    """Merge worker results into a bounded synthesis prompt."""

    def build_prompt(self, query: str, tasks: list[PlannedTask], results: list[TaskResult]) -> str:
        return self.build_prompt_with_context(query=query, tasks=tasks, results=results, context_note=None)

    def build_prompt_with_context(
        self,
        query: str,
        tasks: list[PlannedTask],
        results: list[TaskResult],
        context_note: Optional[str],
    ) -> str:
        evidence_sections = []
        for result in results:
            section = self._format_result(result)
            if section:
                evidence_sections.append(section)

        evidence_blob = "\n\n".join(evidence_sections)
        evidence_blob = self._truncate(evidence_blob, 7000)

        task_list = ", ".join(task.name for task in tasks)
        context_block = ""
        if context_note:
            context_block = f"\n\nConversation context:\n{self._truncate(context_note, 2000)}"

        # Adapt the writing style to the user's expertise (carried in the context
        # note as "expertise_level=<level>"). Beginners get plain language.
        style = (
            "Write a concise, decision-ready answer."
        )
        note = context_note or ""
        if "expertise_level=beginner" in note:
            style = (
                "The reader is a COMPLETE BEGINNER investor. Write in plain, everyday "
                "language: no jargon (or explain any term in brackets the first time), "
                "use short sentences and simple analogies, and after each key point add "
                "the 'so what' — what it means for their money. Prefer 'the company "
                "earns/owes/spends' phrasing over ratio names. End with a one-line "
                "takeaway starting 'In short:'. Keep it friendly but factual, and never "
                "give direct buy/sell advice — frame things as 'a positive sign' or "
                "'a reason for caution'."
            )
        elif "expertise_level=advanced" in note:
            style = (
                "The reader is an advanced analyst: be dense and quantitative, lead with "
                "the numbers, skip explanations of standard terms."
            )
        return (
            "You are synthesizing a research answer from pre-collected evidence. "
            "Do not invent facts that are not present in the evidence. "
            "If the evidence is insufficient, say so clearly.\n\n"
            f"User request:\n{query}\n\n"
            f"{context_block}"
            f"Planned tasks: {task_list}\n\n"
            f"Evidence:\n{evidence_blob}\n\n"
            f"{style}"
        )

    def build_sources(self, results: list[TaskResult]) -> list[dict[str, Any]]:
        return [result.source for result in results]

    def _format_result(self, result: TaskResult) -> str:
        payload_text = self._render_payload(result.payload)
        if not payload_text:
            return ""
        return self._truncate(f"## {result.name}\n{payload_text}", 2200)

    def _render_payload(self, payload: Any) -> str:
        try:
            return json.dumps(payload, indent=2, default=str, ensure_ascii=True)
        except TypeError:
            return str(payload)

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 20] + "\n... [truncated]"

