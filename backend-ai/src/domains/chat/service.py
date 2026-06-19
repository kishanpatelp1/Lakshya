"""Business logic for chat query and session listing."""

import logging
import time
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.agents.guardrails import (
    apply_output_guardrail,
    check_rate_limit,
    validate_input,
)
from src.app.telemetry import traceable
from src.db.models import ChatMessage, ChatSession, NewsArticle, User, Portfolio
from src.utils.cache import get_analysis_cache
from src.utils.data_sources import DataSource

logger = logging.getLogger(__name__)


MAX_AGENT_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.0

# Keywords that make a query portfolio-specific (cache must include user context)
_PORTFOLIO_KEYWORDS = {"my portfolio", "my holdings", "my stocks", "portfolio"}


class ChatService:
    """Encapsulates chat orchestration and persistence logic."""

    def __init__(self, db: Session):
        self.db = db

    def _build_user_message(
        self,
        query: str,
        user_id: UUID,
        expertise_level: str,
        upload_id: Optional[UUID],
        primary_portfolio_id: Optional[UUID],
        news_context: Optional[str] = None,
    ) -> str:
        parts = [query]
        context_lines = [f"user_id={user_id}"]
        if upload_id:
            context_lines.append(f"upload_id={upload_id}")
        if primary_portfolio_id:
            context_lines.append(f"primary_portfolio_id={primary_portfolio_id}")
        context_lines.append(f"expertise_level={expertise_level}")
        parts.append(f"\n\n[Context: {', '.join(context_lines)}]")
        if news_context:
            parts.append(f"\n\n[Recent News & Events for this company — use as context if no filing data is available:\n{news_context}]")
        return "".join(parts)

    @staticmethod
    def _is_portfolio_query(query: str) -> bool:
        q_lower = query.lower()
        return any(kw in q_lower for kw in _PORTFOLIO_KEYWORDS)

    @staticmethod
    def _cache_key(query: str, expertise_level: str, user_id: UUID, portfolio_id: Any) -> str:
        cache = get_analysis_cache()
        q_norm = query.strip().lower()
        if ChatService._is_portfolio_query(query):
            return cache.make_key("chat", q_norm, expertise_level, str(user_id), str(portfolio_id))
        return cache.make_key("chat", q_norm, expertise_level)

    def _fetch_company_news_context(self, company_id: UUID, limit: int = 15) -> Optional[str]:
        """Fetch recent news headlines for a company to inject into agent context."""
        try:
            articles = (
                self.db.query(NewsArticle)
                .filter(NewsArticle.company_id == company_id)
                .order_by(NewsArticle.published_at.desc())
                .limit(limit)
                .all()
            )
            if not articles:
                return None
            lines = []
            for a in articles:
                date_str = a.published_at.strftime("%Y-%m-%d") if a.published_at else "unknown date"
                sentiment = f" [{a.sentiment_label}]" if a.sentiment_label else ""
                source = f" — {a.source}" if a.source else ""
                lines.append(f"• {date_str}{source}{sentiment}: {a.headline}")
            return "\n".join(lines)
        except Exception:
            return None

    @traceable(name="chat.process_query")
    def process_query(
        self,
        user_id: UUID,
        query: str,
        expertise_level: str,
        session_id: Optional[UUID],
        upload_id: Optional[UUID],
        company_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        logger.debug(f"[STAGE 2: SERVICE] process_query called: user_id={user_id}, query='{query[:50]}...'")

        # Guardrails: rate limit + input validation / prompt-injection defence
        check_rate_limit(str(user_id))
        validate_input(query)

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(
                id=user_id,
                email=f"{user_id}@auto.lakshya.dev",
                expertise_level=expertise_level,
            )
            self.db.add(user)
            self.db.flush()
            logger.debug(f"[STAGE 2a: USER] Created new user: {user_id}")
        else:
            logger.debug(f"[STAGE 2a: USER] User exists: {user_id}")

        resolved_session_id = session_id
        if not resolved_session_id:
            session = ChatSession(
                user_id=user_id,
                title=query[:50],
                context_type="general",
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            resolved_session_id = session.id
            logger.debug(f"[STAGE 2b: SESSION] Created new session: {resolved_session_id}")
        else:
            session = (
                self.db.query(ChatSession)
                .filter(
                    ChatSession.id == resolved_session_id,
                    ChatSession.user_id == user_id,
                )
                .first()
            )
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            logger.debug(f"[STAGE 2b: SESSION] Using existing session: {resolved_session_id}")

        primary_portfolio = (
            self.db.query(Portfolio)
            .filter(Portfolio.user_id == user_id, Portfolio.is_primary == True)
            .first()
        )
        primary_portfolio_id = primary_portfolio.id if primary_portfolio else None
        if primary_portfolio_id:
            logger.debug(f"[STAGE 3: PORTFOLIO] Primary portfolio: {primary_portfolio_id}")

        # --- Cache check (skip for document-attached queries) ---
        cache = get_analysis_cache()
        cache_key = None
        if not upload_id:
            cache_key = self._cache_key(query, expertise_level, user_id, primary_portfolio_id)
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"[CACHE HIT] Returning cached response for query='{query[:50]}'")
                # Still save user message / assistant response to DB for session continuity
                self.db.add(ChatMessage(session_id=resolved_session_id, role="user", content=query))
                self.db.add(ChatMessage(
                    session_id=resolved_session_id,
                    role="assistant",
                    content=cached["response_text"],
                    tokens_used=0,
                ))
                self.db.commit()
                return {
                    "response": cached["response_text"],
                    "tokens_used": 0,
                    "session_id": str(resolved_session_id),
                    "data_sources": cached["data_sources"],
                    "cached": True,
                }


        news_context = self._fetch_company_news_context(company_id) if company_id else None
        user_message = self._build_user_message(
            query=query,
            user_id=user_id,
            expertise_level=expertise_level,
            upload_id=upload_id,
            primary_portfolio_id=primary_portfolio_id,
            news_context=news_context,
        )

        logger.debug(f"[STAGE 3: USER_MESSAGE] Built message (full): {user_message}")

        logger.debug(f"[STAGE 4: PIPELINE] Running planner/task-queue/worker-pool flow for session_id={resolved_session_id}")
        result: Optional[dict[str, Any]] = None
        last_err = None
        for attempt in range(1, MAX_AGENT_RETRIES + 1):
            try:
                logger.debug(f"[STAGE 4: ATTEMPT {attempt}/{MAX_AGENT_RETRIES}] Running research pipeline...")

                from src.agents.graph import run_research

                result = run_research(
                    {
                        "query": query,
                        "user_id": str(user_id),
                        "company_id": str(company_id) if company_id else None,
                        "upload_id": str(upload_id) if upload_id else None,
                        "portfolio_id": str(primary_portfolio_id) if primary_portfolio_id else None,
                        "context_note": user_message,
                    },
                    {"configurable": {"thread_id": str(resolved_session_id)}},
                )

                logger.debug(f"[STAGE 4: ATTEMPT {attempt}] Pipeline succeeded")
                last_err = None
                break
            except Exception as invoke_err:
                last_err = invoke_err
                err_msg = str(invoke_err)
                logger.debug(f"[STAGE 4: ATTEMPT {attempt}] Pipeline failed: {err_msg[:200]}")

                if "output_parse_failed" in err_msg or "BadRequestError" in type(invoke_err).__name__:
                    logger.debug(f"[STAGE 4: RETRY] Retrying after {RETRY_BACKOFF_SECONDS * attempt}s...")
                    if attempt < MAX_AGENT_RETRIES:
                        time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                        continue
                raise

        if last_err is not None:
            raise last_err
        if result is None:
            raise RuntimeError("Pipeline returned no result")

        logger.debug(f"[STAGE 4: RESULT_FULL] result keys = {list(result.keys())}")

        response_text = apply_output_guardrail(result["response"])
        logger.debug(f"[STAGE 4: LLM_RESPONSE_FULL] response_text = {response_text}")

        tokens_used = int(result.get("tokens_used", 0))
        if tokens_used:
            logger.debug(f"[STAGE 4: TOKENS_USED] tokens_used = {tokens_used}")

        self.db.add(
            ChatMessage(
                session_id=resolved_session_id,
                role="user",
                content=query,
            )
        )
        self.db.add(
            ChatMessage(
                session_id=resolved_session_id,
                role="assistant",
                content=response_text,
                tokens_used=tokens_used,
            )
        )
        self.db.commit()

        logger.debug(f"[STAGE 5: DB] Messages saved to DB, session={resolved_session_id}")

        data_sources = result.get("data_sources") or [
            DataSource(
                name="Planner-driven research pipeline",
                url=f"/chat/sessions/{user_id}",
                data_type="ai_response",
            ).model_dump(),
        ]

        # Store in cache for future identical queries
        if cache_key:
            cache.set(cache_key, {
                "response_text": response_text,
                "data_sources": data_sources,
            })
            logger.debug(f"[CACHE SET] Stored response under key {cache_key[:24]}...")

        return {
            "response": response_text,
            "tokens_used": tokens_used,
            "session_id": str(resolved_session_id),
            "sources": result.get("sources", []),
            "visualizations": result.get("visualizations", []),
            "data_sources": data_sources,
        }

    def stream_query(
        self,
        user_id: UUID,
        query: str,
        expertise_level: str,
        session_id: Optional[UUID],
        upload_id: Optional[UUID] = None,
        company_id: Optional[UUID] = None,
    ):
        """Yield Server-Sent Events (stage / token / done / error) for a query.

        Reuses the same planner/evidence step as ``process_query`` but streams
        the synthesis tokens instead of blocking on the full answer.
        """
        import json

        from src.agents.graph import build_research_graph, stream_research

        def sse(event: str, data: dict[str, Any]) -> str:
            return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

        try:
            # Guardrails: rate limit + input validation / prompt-injection defence
            check_rate_limit(str(user_id))
            validate_input(query)

            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                user = User(
                    id=user_id,
                    email=f"{user_id}@auto.lakshya.dev",
                    expertise_level=expertise_level,
                )
                self.db.add(user)
                self.db.flush()

            resolved_session_id = session_id
            if not resolved_session_id:
                session = ChatSession(user_id=user_id, title=query[:50], context_type="general")
                self.db.add(session)
                self.db.commit()
                self.db.refresh(session)
                resolved_session_id = session.id
            else:
                session = (
                    self.db.query(ChatSession)
                    .filter(ChatSession.id == resolved_session_id, ChatSession.user_id == user_id)
                    .first()
                )
                if not session:
                    yield sse("error", {"detail": "Session not found"})
                    return

            primary_portfolio = (
                self.db.query(Portfolio)
                .filter(Portfolio.user_id == user_id, Portfolio.is_primary == True)
                .first()
            )
            primary_portfolio_id = primary_portfolio.id if primary_portfolio else None

            news_context = self._fetch_company_news_context(company_id) if company_id else None
            user_message = self._build_user_message(
                query=query,
                user_id=user_id,
                expertise_level=expertise_level,
                upload_id=upload_id,
                primary_portfolio_id=primary_portfolio_id,
                news_context=news_context,
            )

            inputs = {
                "query": query,
                "user_id": str(user_id),
                "company_id": str(company_id) if company_id else None,
                "upload_id": str(upload_id) if upload_id else None,
                "portfolio_id": str(primary_portfolio_id) if primary_portfolio_id else None,
                "context_note": user_message,
            }
            config = {"configurable": {"thread_id": str(resolved_session_id)}}

            parts: list[str] = []
            for kind, data in stream_research(inputs, config):
                if kind == "stage":
                    yield sse("stage", data)
                elif kind == "token":
                    parts.append(data)
                    yield sse("token", {"text": data})

            raw_text = "".join(parts)
            response_text = apply_output_guardrail(raw_text)
            # Stream the appended disclaimer so the client shows the guarded text.
            if response_text.startswith(raw_text) and len(response_text) > len(raw_text):
                yield sse("token", {"text": response_text[len(raw_text):]})

            self.db.add(ChatMessage(session_id=resolved_session_id, role="user", content=query))
            self.db.add(
                ChatMessage(
                    session_id=resolved_session_id,
                    role="assistant",
                    content=response_text,
                    tokens_used=0,
                )
            )
            self.db.commit()

            # Sources come from the graph's final persisted state.
            gstate = build_research_graph().get_state(config)
            sources = gstate.values.get("sources", []) if gstate else []
            yield sse("done", {"session_id": str(resolved_session_id), "sources": sources})
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            yield sse("error", {"detail": str(e)})

    def get_messages(self, session_id: UUID, user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        """Return the messages of a session, but only if the user owns it."""
        session = (
            self.db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if not session:
            return []
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]

    def list_sessions(self, user_id: UUID, limit: int) -> list[dict[str, Any]]:
        sessions = (
            self.db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(session.id),
                "title": session.title,
                "context_type": session.context_type,
                "last_message_at": (
                    session.last_message_at.isoformat() if session.last_message_at else None
                ),
                "created_at": session.created_at.isoformat(),
            }
            for session in sessions
        ]
