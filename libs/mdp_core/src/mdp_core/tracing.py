"""OpenTelemetry setup, shared by every service.

Metrics tell you a pipeline is slow. Traces tell you which hop is slow. This
pipeline has five of them — feed, producer, broker, Flink, ClickHouse — and
"latency went up" is not an actionable statement without knowing which.

Tracing is opt-in via OTEL_EXPORTER_OTLP_ENDPOINT. Unset, this is a no-op and
the services run exactly as before: nobody should need a collector running to
use the project.
"""

from __future__ import annotations

import os

import structlog

log = structlog.get_logger(__name__)


def configure_tracing(service_name: str) -> bool:
    """Wire up OTLP export. Returns True if tracing is active.

    Reads the endpoint through Settings rather than os.environ, so it picks up
    .env exactly like every other setting. Reading the raw environment meant
    the services silently ran untraced whenever they were started outside
    `just`, which is how this was first missed.
    """
    from mdp_core.config import get_settings

    endpoint = (
        get_settings().otel_exporter_otlp_endpoint
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    ).strip()
    if not endpoint:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        # The OTel packages are an extra. Say so rather than failing to start.
        log.warning("tracing_unavailable", reason="opentelemetry packages not installed")
        return False

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "service.namespace": "market-data-pipeline",
            }
        )
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces"))
    )
    trace.set_tracer_provider(provider)
    log.info("tracing_enabled", service=service_name, endpoint=endpoint)
    return True


def tracer(name: str):  # type: ignore[no-untyped-def]
    """Return a tracer. Safe to call whether or not tracing is configured."""
    from opentelemetry import trace

    return trace.get_tracer(name)
