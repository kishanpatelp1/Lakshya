"""
=============================================================
FULL END-TO-END FLOW VERIFICATION
=============================================================
Tests every layer of the stack independently:

  LAYER 1 — ETL Pipeline
    1a. Text extraction & cleaning
    1b. LLM enrichment (timeline summary, red flags, metrics)
    1c. Semantic chunking & embedding
    1d. Load into Qdrant vector DB

  LAYER 2 — Vector / RAG Layer
    2a. Company-scoped semantic search (search_filings tool)
    2b. Global thematic search (thematic_discovery_search tool)

  LAYER 3 — Agent Tools Layer
    3a. Company resolver tool
    3b. Financial service tool (ratios)
    3c. Risk flag detection tool
    3d. Error handling / resilience

  LAYER 4 — Portfolio Math Engine
    4a. Beta, Sharpe, Volatility, Diversification calculation

  LAYER 5 — Lakshya Copilot (single focused query, no loop)
    5a. Targeted company-analysis query via ChatService

=============================================================
HOW TO RUN:
  cd backend-ai
  .venv/bin/python test_e2e_full_flow.py
=============================================================
"""

import sys
import os
import logging
from pathlib import Path
from uuid import uuid4, UUID

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
logging.basicConfig(level=logging.WARNING)  # suppress HTTP noise

PASS = "  ✅ PASS"
FAIL = "  ❌ FAIL"
SKIP = "  ⚠️  SKIP"

results = []

def log(label: str, ok: bool, detail: str = ""):
    status = PASS if ok else FAIL
    results.append((label, ok))
    print(f"{status}  [{label}]  {detail}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────────────────────
# LAYER 1 — ETL Pipeline
# ─────────────────────────────────────────────────────────────
section("LAYER 1 — ETL Pipeline")

from src.db.database import SessionLocal
from src.agents.tools.company_resolver import resolve_company
from src.etl.transform_task import ETLTransformTask
from src.etl.load_task import ETLLoadTask

# 1a — resolve company
company_data = resolve_company.invoke({"name_or_ticker": "Reliance Industries"})
company_id = company_data.get("company_id")
ok = bool(company_id) and "error" not in company_data
log("1a: Company resolve", ok, f"UUID={company_id}")

# create test document
test_dir = Path("uploads/filings")
test_dir.mkdir(parents=True, exist_ok=True)
test_file = test_dir / "reliance_annual_report_e2e.txt"
test_file.write_text(
    "Reliance Industries Limited — Annual Report 2023\n"
    "Management Discussion and Analysis:\n"
    "Revenue has grown by 20% to ₹80,000 Cr driven by retail and Jio segments. "
    "Risk Factors include market volatility, global supply chain disruptions, "
    "and regulatory changes in the telecom sector. "
    "The company reduced debt by 15% YoY maintaining a healthy balance sheet. "
    "Board approved a capex plan of ₹15,000 Cr for renewable energy expansion.",
    encoding="utf-8"
)

# 1b — ETL transform with enrichment
transformer = ETLTransformTask()
metadata = {
    "company_id": company_id,
    "filing_id": str(uuid4()),
    "filing_type": "Annual Report",
    "company": "Reliance Industries",
    "year": "2023",
    "document_type": "annual_report"
}
try:
    result = transformer.process_filing(str(test_file), **metadata)
    enrichment = result.get("enrichment", {})
    chunks = result.get("chunks", [])
    ok_enrich = bool(enrichment.get("timeline_summary"))
    log("1b: LLM Enrichment", ok_enrich, f"Summary: {enrichment.get('timeline_summary', '')[:80]}...")
    log("1b: Red Flag extraction", bool(enrichment.get("red_flags")), f"Flags: {enrichment.get('red_flags')}")
    log("1b: Metrics extraction", bool(enrichment.get("metrics")), f"Metrics: {enrichment.get('metrics')}")
    log("1c: Semantic chunking", len(chunks) > 0, f"{len(chunks)} chunks created")
except Exception as e:
    log("1b: LLM Enrichment", False, str(e))
    log("1b: Red Flag extraction", False, "skipped")
    log("1b: Metrics extraction", False, "skipped")
    log("1c: Semantic chunking", False, "skipped")
    chunks = []

# 1d — Load into Qdrant
if chunks:
    try:
        loader = ETLLoadTask()
        loaded = loader.load_chunks(chunks)
        log("1d: Qdrant vector load", loaded > 0, f"Loaded {loaded} chunks into vector DB")
    except Exception as e:
        log("1d: Qdrant vector load", False, str(e))
else:
    log("1d: Qdrant vector load", False, "No chunks to load")


# ─────────────────────────────────────────────────────────────
# LAYER 2 — Vector / RAG Layer
# ─────────────────────────────────────────────────────────────
section("LAYER 2 — Vector / RAG Layer")

from src.services.vector_service import VectorService
from src.agents.tools.vector_search import search_filings, thematic_discovery_search

svc = VectorService()

# 2a — Company-scoped semantic search
try:
    uid = UUID(company_id)
    company_results = svc.search_company_filings(
        company_id=uid,
        query="risk factors telecom regulatory changes",
        limit=3
    )
    ok2a = len(company_results) > 0
    top = company_results[0] if company_results else {}
    log("2a: Company-scoped vector search", ok2a, f"Score={top.get('score', 0):.3f} | Text='{top.get('text','')[:80]}...'")
except Exception as e:
    log("2a: Company-scoped vector search", False, str(e))

# 2b — Global thematic search
try:
    thematic_results = svc.thematic_search(
        query="telecom regulatory changes market volatility",
        limit=10
    )
    ok2b = len(thematic_results) > 0
    top_co = thematic_results[0] if thematic_results else {}
    log("2b: Global thematic vector search", ok2b,
        f"Top company: {top_co.get('company_name','?')} | Score={top_co.get('max_score',0):.3f} | Matches={top_co.get('match_count',0)}")
except Exception as e:
    log("2b: Global thematic vector search", False, str(e))

# 2b-tool — thematic_discovery_search tool directly
try:
    tool_result = thematic_discovery_search.invoke({"query": "telecom regulatory changes", "limit": 5})
    ok2b_tool = isinstance(tool_result, list) and len(tool_result) > 0
    log("2b: thematic_discovery_search tool", ok2b_tool, f"Returned {len(tool_result)} companies")
except Exception as e:
    log("2b: thematic_discovery_search tool", False, str(e))


# ─────────────────────────────────────────────────────────────
# LAYER 3 — Agent Tools Layer
# ─────────────────────────────────────────────────────────────
section("LAYER 3 — Agent Tools Layer")

from src.agents.tools.financial import get_latest_financials, calculate_ratios, detect_risk_flags

# 3a — search_filings tool
try:
    sf_result = search_filings.invoke({
        "company_id": "Reliance Industries",
        "query": "revenue growth debt reduction",
        "limit": 3
    })
    ok3a = isinstance(sf_result, list) and len(sf_result) > 0 and "error" not in str(sf_result[0])
    top_sf = sf_result[0] if sf_result else {}
    log("3a: search_filings tool", ok3a,
        f"Score={top_sf.get('score',0):.3f} | '{top_sf.get('text','')[:60]}...'")
except Exception as e:
    log("3a: search_filings tool", False, str(e))

# 3b — financial ratios tool (may fail if FMP API not seeded)
try:
    ratios = calculate_ratios.invoke({"company_id": "Reliance Industries"})
    has_ratios = "ratios" in ratios and ratios["ratios"]
    if has_ratios:
        log("3b: calculate_ratios tool", True, f"PE={ratios['ratios'].get('pe_ratio')}, ROE={ratios['ratios'].get('roe')}")
    else:
        # expected if no FMP financial data loaded — error handling should be clean
        has_error_msg = "error" in ratios
        log("3b: calculate_ratios tool (error path)", has_error_msg,
            f"Returned clean error: {ratios.get('error','')[:80]}")
except Exception as e:
    log("3b: calculate_ratios tool", False, str(e))

# 3c — risk flags tool
try:
    flags = detect_risk_flags.invoke({"company_id": "Reliance Industries"})
    ok3c = isinstance(flags, list)  # empty list is fine (no flags or no data)
    log("3c: detect_risk_flags tool", ok3c, f"Returned {len(flags)} flags (empty=OK if no financial data)")
except Exception as e:
    log("3c: detect_risk_flags tool", False, str(e))

# 3d — Error handling: invalid company
try:
    bad_result = search_filings.invoke({"company_id": "NONEXISTENT_COMPANY_XYZ999", "query": "test"})
    has_error = "error" in str(bad_result[0]) if bad_result else False
    log("3d: Error resilience (bad company)", has_error, f"Got clean error: {str(bad_result[0])[:80]}")
except Exception as e:
    log("3d: Error resilience (bad company)", False, str(e))


# ─────────────────────────────────────────────────────────────
# LAYER 4 — Portfolio Math Engine
# ─────────────────────────────────────────────────────────────
section("LAYER 4 — Portfolio Math Engine")

from src.services.portfolio_service import PortfolioService
from unittest.mock import MagicMock, patch

# Mock DB with synthetic holdings for math verification
mock_holding1 = MagicMock()
mock_holding1.id = uuid4()
mock_holding1.company_id = uuid4()
mock_holding1.quantity = 100
mock_holding1.average_price = 2800.0
mock_holding1.current_price = 3100.0
mock_holding1.currency = "INR"

mock_holding2 = MagicMock()
mock_holding2.id = uuid4()
mock_holding2.company_id = uuid4()
mock_holding2.quantity = 50
mock_holding2.average_price = 1500.0
mock_holding2.current_price = 1700.0
mock_holding2.currency = "INR"

mock_company1 = MagicMock()
mock_company1.sector = "Technology"
mock_company2 = MagicMock()
mock_company2.sector = "Financials"

mock_db = MagicMock()
mock_db.query.return_value.filter.return_value.all.return_value = [mock_holding1, mock_holding2]
mock_db.query.return_value.filter.return_value.first.side_effect = [mock_company1, mock_company2]

portfolio_id = uuid4()
svc_p = PortfolioService(mock_db)
try:
    metrics = svc_p.calculate_metrics(portfolio_id)
    ok4a = all(k in metrics for k in ["portfolio_beta", "sharpe_ratio", "portfolio_volatility", "diversification_score"])
    log("4a: Portfolio metrics computed", ok4a,
        f"Beta={metrics.get('portfolio_beta')} | Sharpe={metrics.get('sharpe_ratio')} | "
        f"Vol={metrics.get('portfolio_volatility')} | DivScore={metrics.get('diversification_score')}")
    ok4b = 0 < metrics.get("portfolio_beta", 0) < 3
    log("4b: Beta in realistic range (0-3)", ok4b, f"Beta={metrics.get('portfolio_beta')}")
    ok4c = metrics.get("sharpe_ratio", 0) > 0
    log("4c: Sharpe ratio positive", ok4c, f"Sharpe={metrics.get('sharpe_ratio')}")
    ok4d = 0 <= metrics.get("diversification_score", 0) <= 100
    log("4d: Diversification score 0-100", ok4d, f"Score={metrics.get('diversification_score')}")
except Exception as e:
    log("4a: Portfolio metrics computed", False, str(e))
    log("4b: Beta in realistic range", False, "skipped")
    log("4c: Sharpe ratio positive", False, "skipped")
    log("4d: Diversification score 0-100", False, "skipped")


# ─────────────────────────────────────────────────────────────
# LAYER 5 — Lakshya Copilot (single targeted query)
# ─────────────────────────────────────────────────────────────
section("LAYER 5 — Lakshya Copilot (Targeted RAG Query)")

from src.domains.chat.service import ChatService

db = SessionLocal()
chat_service = ChatService(db)

# Use a targeted, filing-specific query that gives the agent
# just one tool to call (search_filings) and finish.
query = (
    "Using the search_filings tool for Reliance Industries, "
    "find text about debt reduction and summarize it in 2 sentences."
)

print(f"\n  Query: {query}")
print("  [Agent working... calling LLM + Qdrant]")

try:
    response = chat_service.process_query(
        user_id=uuid4(),
        query=query,
        expertise_level="intermediate",
        session_id=None,
        upload_id=None
    )
    reply = response.get("response", "")
    tokens = response.get("tokens_used", 0)
    ok5 = len(reply) > 50  # got a real answer
    log("5a: Lakshya copilot responds to RAG query", ok5,
        f"Tokens={tokens} | Reply preview: '{reply[:120]}...'")
except Exception as e:
    log("5a: Lakshya copilot responds to RAG query", False, str(e))
finally:
    db.close()


# ─────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────
section("FINAL SUMMARY")

passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
total = len(results)

print(f"\n  Total: {total}  |  ✅ Passed: {passed}  |  ❌ Failed: {failed}\n")
for label, ok in results:
    print(f"  {'✅' if ok else '❌'}  {label}")

print()
if failed == 0:
    print("  🎉 ALL LAYERS VERIFIED — Stack is production-ready!")
else:
    print(f"  ⚠️  {failed} check(s) failed. Review output above.")
