from __future__ import annotations

import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_configured = False


def _provider(service_name: str) -> TracerProvider:
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if endpoint:
        exporter = OTLPSpanExporter(
            endpoint=f"{endpoint.rstrip('/')}/v1/traces"
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def configure_tracing(app: FastAPI) -> None:
    global _configured
    if _configured:
        return
    provider = _provider(os.getenv("CIIS_ROLE", "ciis-api"))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)

    try:
        SQLAlchemyInstrumentor().instrument()
    except Exception:
        pass
    _configured = True


def configure_worker_tracing() -> None:
    global _configured
    if _configured:
        return
    provider = _provider(os.getenv("CIIS_ROLE", "ciis-worker"))
    trace.set_tracer_provider(provider)
    try:
        SQLAlchemyInstrumentor().instrument()
    except Exception:
        pass
    _configured = True


def get_tracer(name: str):
    return trace.get_tracer(name)
