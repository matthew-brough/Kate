"""OpenTelemetry setup.

Wires a TracerProvider backed by either the OTLP gRPC exporter (production)
or the console exporter (local, when OTLP is disabled).  FastAPI is
auto-instrumented so every request gets a span with no manual decoration.
"""

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.settings import settings


def configure_telemetry(app: FastAPI) -> None:
    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.service_version,
            "deployment.environment": settings.env,
        }
    )

    provider = TracerProvider(resource=resource)

    if settings.otlp_enabled:
        exporter: OTLPSpanExporter | ConsoleSpanExporter = OTLPSpanExporter(
            endpoint=settings.otlp_endpoint,
            insecure=True,
        )
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
