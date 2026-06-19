"""Observability helpers for OpenTelemetry and LangSmith."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

from fastapi import FastAPI

from src.config import Settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency guard
    from langsmith import traceable as _langsmith_traceable
except Exception:  # pragma: no cover - optional dependency guard
    _langsmith_traceable = None

try:  # pragma: no cover - optional dependency guard
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    except Exception:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        OTLPLogExporter = None
except Exception:  # pragma: no cover - optional dependency guard
    trace = None
    OTLPSpanExporter = None
    OTLPLogExporter = None
    FastAPIInstrumentor = None
    HTTPXClientInstrumentor = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    ConsoleSpanExporter = None
    LoggerProvider = None
    LoggingHandler = None
    BatchLogRecordProcessor = None

_otel_initialized = False
_httpx_initialized = False
_log_initialized = False


def traceable(*decorator_args: Any, **decorator_kwargs: Any):
    """Return the LangSmith traceable decorator when available."""
    if _langsmith_traceable is None:
        if decorator_args and callable(decorator_args[0]) and len(decorator_args) == 1 and not decorator_kwargs:
            return decorator_args[0]

        def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return _decorator

    return _langsmith_traceable(*decorator_args, **decorator_kwargs)


def _set_env(name: str, value: Any, force: bool = False) -> None:
    """Set an environment variable.

    When *force* is True the value is always written (overwriting any existing
    value).  When False (default) it only writes if the variable is not already
    set, unless the current value is empty.
    """
    if value is None or value == "":
        return
    str_val = str(value)
    if force or not os.environ.get(name):
        os.environ[name] = str_val


def _parse_headers(raw_headers: str | None) -> dict[str, str] | None:
    if not raw_headers:
        return None

    headers: dict[str, str] = {}
    for item in raw_headers.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            headers[key] = value
    return headers or None


def configure_observability(settings: Settings) -> None:
    """Configure LangSmith and OpenTelemetry from settings.

    Environment variables are written **before** any ``langchain`` imports so
    that ``langchain-core``'s internal tracer picks them up automatically.
    Both the modern ``LANGSMITH_*`` and the legacy ``LANGCHAIN_*`` variable
    names are set for maximum compatibility.
    """
    # ── LangSmith / LangChain tracing ──────────────────────────────────
    # ``LANGCHAIN_TRACING_V2`` is the flag that ``langchain-core`` checks
    # at import time to decide whether to create a ``LangSmithV1`` tracer.
    tracing = settings.langsmith_tracing
    tracing_flag = str(tracing).lower() if isinstance(tracing, bool) else str(tracing)

    _set_env("LANGSMITH_TRACING", tracing_flag, force=True)
    _set_env("LANGCHAIN_TRACING_V2", tracing_flag, force=True)

    _set_env("LANGSMITH_PROJECT", settings.langsmith_project, force=True)
    _set_env("LANGCHAIN_PROJECT", settings.langsmith_project, force=True)

    _set_env("LANGSMITH_ENDPOINT", settings.langsmith_endpoint, force=True)
    _set_env("LANGCHAIN_ENDPOINT", settings.langsmith_endpoint, force=True)

    _set_env("LANGSMITH_API_KEY", settings.langsmith_api_key, force=True)
    _set_env("LANGCHAIN_API_KEY", settings.langsmith_api_key, force=True)

    # ── OpenTelemetry ──────────────────────────────────────────────────
    _set_env("OTEL_SERVICE_NAME", settings.observability_service_name, force=True)
    _set_env("OTEL_SERVICE_VERSION", settings.observability_service_version, force=True)
    _set_env("OTEL_EXPORTER_OTLP_ENDPOINT", settings.otel_exporter_otlp_endpoint, force=True)
    _set_env("OTEL_EXPORTER_OTLP_PROTOCOL", settings.otel_exporter_otlp_protocol, force=True)
    # A plaintext http:// gRPC endpoint (local collector) needs insecure mode,
    # otherwise the exporter attempts TLS and every export fails silently.
    if (settings.otel_exporter_otlp_endpoint or "").startswith("http://"):
        _set_env("OTEL_EXPORTER_OTLP_INSECURE", "true", force=True)

    if not (settings.observability_enabled or settings.otel_exporter_otlp_endpoint):
        return

    _configure_tracer_provider(settings)
    _configure_log_provider(settings)
    _instrument_httpx()


def _configure_tracer_provider(settings: Settings) -> None:
    global _otel_initialized
    if _otel_initialized or trace is None:
        return

    resource = Resource.create(
        {
            "service.name": settings.observability_service_name,
            "service.version": settings.observability_service_version,
        }
    )
    provider = TracerProvider(resource=resource)

    exporter = None
    if settings.otel_exporter_otlp_endpoint and OTLPSpanExporter is not None:
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
        )
    elif ConsoleSpanExporter is not None:
        exporter = ConsoleSpanExporter()

    if exporter is None or BatchSpanProcessor is None:
        logger.warning("OpenTelemetry exporter unavailable; tracing will stay disabled.")
        return

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _otel_initialized = True


def _configure_log_provider(settings: Settings) -> None:
    """Wire Python ``logging`` logs through OTLP to SigNoz."""
    global _log_initialized
    if _log_initialized or LoggerProvider is None:
        return

    endpoint = settings.otel_exporter_otlp_endpoint
    if not endpoint or OTLPLogExporter is None:
        return

    resource = Resource.create(
        {
            "service.name": settings.observability_service_name,
            "service.version": settings.observability_service_version,
        }
    )
    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint))
    )

    handler = LoggingHandler(level=logging.NOTSET, logger_provider=log_provider)
    handler.setLevel(logging.DEBUG)

    root = logging.getLogger()
    root.addHandler(handler)

    _log_initialized = True
    logger.info("OTel log export configured -> %s", endpoint)


def _instrument_httpx() -> None:
    global _httpx_initialized
    if _httpx_initialized or HTTPXClientInstrumentor is None:
        return

    HTTPXClientInstrumentor().instrument()
    _httpx_initialized = True


def instrument_fastapi(app: FastAPI) -> None:
    """Attach OpenTelemetry middleware to a FastAPI app when available."""
    if FastAPIInstrumentor is None:
        return
    if getattr(app.state, "otel_instrumented", False):
        return

    FastAPIInstrumentor.instrument_app(app)
    app.state.otel_instrumented = True