"""Request-scoped context helpers for correlation IDs and flow events."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict, List

_request_context: ContextVar[Dict[str, Any]] = ContextVar(
    "request_context",
    default={"request_id": None, "flow_events": []},
)


def clear_request_context() -> None:
    """Reset request-scoped state so no data leaks across requests."""
    _request_context.set({"request_id": None, "flow_events": []})


def set_request_id(request_id: str) -> None:
    """Store request id in context for log correlation."""
    _request_context.set({"request_id": request_id, "flow_events": []})


def get_request_id() -> str | None:
    """Fetch current request id from context."""
    value = _request_context.get()
    return value.get("request_id")


def append_flow_event(event: Dict[str, Any]) -> None:
    """Append an event to request flow context."""
    value = _request_context.get()
    events: List[Dict[str, Any]] = list(value.get("flow_events", []))
    events.append(event)
    _request_context.set(
        {
            "request_id": value.get("request_id"),
            "flow_events": events,
        }
    )


def get_flow_events() -> List[Dict[str, Any]]:
    """Get all collected flow events for the current request."""
    value = _request_context.get()
    return list(value.get("flow_events", []))
