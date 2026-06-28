"""Minimal FastAPI app that creates one manual OTel span + logs.

Run:
    cd backend-ai
    python scripts/verify_otel.py

Then open http://localhost:4320/docs and hit GET /demo.
Traces and logs appear in SigNoz at http://localhost:3301.
"""

import logging
import time

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

OTLP_ENDPOINT = "http://localhost:4317"

# ── Configure OTel ──────────────────────────────────────────────────────
resource = Resource.create(
    {
        "service.name": "verify-otel",
        "service.version": "0.0.1",
    }
)

# Traces
tp = TracerProvider(resource=resource)
tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT)))
trace.set_tracer_provider(tp)
tracer = trace.get_tracer("verify-otel")

# Logs
lp = LoggerProvider(resource=resource)
lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTLP_ENDPOINT)))
otel_handler = LoggingHandler(level=logging.NOTSET, logger_provider=lp)
otel_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(otel_handler)
logging.getLogger().setLevel(logging.DEBUG)

log = logging.getLogger("verify-otel")

app = FastAPI(title="OTel Verification")


@app.get("/demo")
def demo():
    """Create a manual span with nested child + log messages."""
    log.info("Handling /demo request")
    with tracer.start_as_current_span("demo-work") as span:
        span.set_attribute("input.greeting", "hello")
        time.sleep(0.05)
        log.info("Starting child computation")
        child = tracer.start_span("child-computation")
        child.set_attribute("result", 42)
        child.end()
        log.info("Child computation complete")
        return {"status": "trace + logs sent to SigNoz", "span_name": "demo-work"}


@app.get("/health")
def health():
    return {"status": "ok"}
