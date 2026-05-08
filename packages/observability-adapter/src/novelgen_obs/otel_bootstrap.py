"""OpenTelemetry bootstrap for AgentCore Observability.

Call `init_observability(service_name, env)` once at process start (before any
tracer is acquired). Idempotent.

Exports:
- Traces via OTLP gRPC to `OTEL_EXPORTER_OTLP_ENDPOINT` (default http://localhost:4318
  which the AgentCore Runtime sidecar serves). Falls back to ConsoleSpanExporter if the
  OTLP exporter cannot be loaded — we never block process startup on telemetry.
- Metrics via OTLP gRPC (same endpoint). Falls back to a no-op meter provider.
- Propagator: AWS X-Ray.

Design notes:
- We intentionally import otel modules lazily so the bootstrap remains optional for
  unit tests and lambdas that don't need it.
- Emit a single startup log line so operators can confirm telemetry wiring.
"""

from __future__ import annotations

import logging
import os
from typing import Any

_INITIALIZED = False
_log = logging.getLogger("novelgen_obs.otel_bootstrap")


def init_observability(service_name: str, env: str = "dev") -> None:
    """Initialize OTEL tracer/meter providers. Idempotent.

    Args:
        service_name: Service identifier (e.g. "worker-analysis"); becomes OTEL resource.service.name.
        env: Environment (dev/prod); becomes deployment.environment.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    try:
        from opentelemetry import propagate, trace  # type: ignore[import-not-found]
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError as e:
        _log.warning(
            "otel sdk not installed (%s); telemetry disabled", e
        )
        _INITIALIZED = True
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "novelgen",
            "deployment.environment": env,
        }
    )

    tracer_provider = TracerProvider(resource=resource)

    span_exporter: Any
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,
        )
        span_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=endpoint.startswith("http://"))
    except ImportError:
        _log.warning("otlp exporter not available; falling back to ConsoleSpanExporter")
        span_exporter = ConsoleSpanExporter()

    tracer_provider.add_span_processor(
        BatchSpanProcessor(span_exporter, max_export_batch_size=512, schedule_delay_millis=5000)
    )
    trace.set_tracer_provider(tracer_provider)

    # AWS X-Ray propagator so trace IDs interop with AgentCore Runtime native traces
    try:
        from opentelemetry.propagators.aws.aws_xray_propagator import (  # type: ignore[import-not-found]
            AwsXRayPropagator,
        )
        propagate.set_global_textmap(AwsXRayPropagator())
    except ImportError:
        _log.debug("aws-xray propagator not available; using default")

    _init_metrics(resource, endpoint)

    _log.info(
        "otel initialized",
        extra={"service": service_name, "env": env, "endpoint": endpoint},
    )
    _INITIALIZED = True


def _init_metrics(resource: Any, endpoint: str) -> None:
    try:
        from opentelemetry import metrics  # type: ignore[import-not-found]
        from opentelemetry.sdk.metrics import MeterProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.metrics.export import (  # type: ignore[import-not-found]
            PeriodicExportingMetricReader,
        )
    except ImportError:
        return

    try:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (  # type: ignore[import-not-found]
            OTLPMetricExporter,
        )
        exporter = OTLPMetricExporter(endpoint=endpoint, insecure=endpoint.startswith("http://"))
    except ImportError:
        return

    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60_000)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))


__all__ = ["init_observability"]
