"""
OpenTelemetry Distributed Tracing

Provides trace instrumentation for analyzing request flows through
the agent pipeline with correlation across API requests and background jobs.
"""

import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager
from functools import wraps

# OpenTelemetry is an optional dependency. This module is imported
# unconditionally by chains.async_orchestrator — including when tracing is
# disabled — so a missing package must not raise at import time, or /analyze
# fails with ModuleNotFoundError at request time rather than at startup.
TRACING_AVAILABLE = True
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.trace import Status, StatusCode, Span
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
except ImportError:  # pragma: no cover - depends on optional extra
    trace = None
    TracerProvider = SpanProcessor = BatchSpanProcessor = None
    Resource = SERVICE_NAME = None
    Status = StatusCode = Span = None
    TraceContextTextMapPropagator = None
    TRACING_AVAILABLE = False

# The OTLP gRPC exporter ships in a *separate* distribution
# (opentelemetry-exporter-otlp), so it is guarded independently: the SDK can be
# present while the exporter is not.
OTLP_EXPORTER_AVAILABLE = False
if TRACING_AVAILABLE:
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        OTLP_EXPORTER_AVAILABLE = True
    except ImportError:  # pragma: no cover - depends on optional extra
        OTLPSpanExporter = None
else:
    OTLPSpanExporter = None

logger = logging.getLogger(__name__)

# Global tracer. Deliberately unannotated: a module-level annotation such as
# Optional[trace.Tracer] is evaluated at import time and would raise when
# OpenTelemetry is not installed (trace is None).
_tracer = None
_tracer_provider = None


def init_tracing(
    service_name: str = "adapt-agents",
    otlp_endpoint: Optional[str] = None,
    enable_console_export: bool = False
) -> bool:
    """
    Initialize OpenTelemetry tracing

    Args:
        service_name: Name of the service for trace identification
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
        enable_console_export: Whether to also export traces to console

    Returns:
        True if tracing initialized successfully, False otherwise
    """
    global _tracer, _tracer_provider

    if not TRACING_AVAILABLE:
        logger.info(
            "OpenTelemetry is not installed; tracing disabled. "
            "Install it with: pip install 'adapt-agents[monitoring]'"
        )
        return False

    try:
        # Create resource with service information
        resource = Resource(attributes={
            SERVICE_NAME: service_name,
            "service.version": "3.5.0",
            "deployment.environment": "production"
        })

        # Create tracer provider
        _tracer_provider = TracerProvider(resource=resource)

        # Add OTLP exporter if endpoint provided
        if otlp_endpoint:
            if not OTLP_EXPORTER_AVAILABLE:
                logger.warning(
                    "otel_endpoint is configured but the OTLP exporter is not installed. "
                    "Install it with: pip install opentelemetry-exporter-otlp. "
                    "Continuing with tracing enabled but no span export."
                )
            else:
                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
                span_processor = BatchSpanProcessor(otlp_exporter)
                _tracer_provider.add_span_processor(span_processor)
                logger.info(f"OTLP exporter configured: {otlp_endpoint}")

        # Add console exporter if requested (for debugging)
        if enable_console_export:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            console_exporter = ConsoleSpanExporter()
            _tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
            logger.info("Console span exporter enabled")

        # Set global tracer provider
        trace.set_tracer_provider(_tracer_provider)

        # Create tracer
        _tracer = trace.get_tracer(__name__)

        logger.info(f"OpenTelemetry tracing initialized for service: {service_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry tracing: {e}")
        return False


class _NoOpSpan:
    """Minimal span stand-in used when OpenTelemetry is unavailable."""

    def set_attribute(self, *args, **kwargs): pass
    def add_event(self, *args, **kwargs): pass
    def record_exception(self, *args, **kwargs): pass
    def set_status(self, *args, **kwargs): pass
    def is_recording(self) -> bool: return False
    def __enter__(self): return self
    def __exit__(self, *exc_info): return False


class _NoOpTracer:
    """Tracer stand-in that yields no-op spans."""

    def start_as_current_span(self, *args, **kwargs):
        return _NoOpSpan()


def get_tracer():
    """
    Get the global tracer instance.

    Never returns None. If OpenTelemetry is absent, or initialization failed
    (bad endpoint, missing exporter), return a no-op tracer instead. Returning
    None would make trace_span raise AttributeError and take down the
    orchestrator hot path it wraps.
    """
    global _tracer

    if not TRACING_AVAILABLE:
        return _NoOpTracer()

    if _tracer is None:
        # Initialize with defaults if not already initialized
        init_tracing()

    if _tracer is None:
        return trace.get_tracer(__name__)

    return _tracer


def shutdown_tracing():
    """Shutdown tracing and flush pending spans"""
    global _tracer_provider

    if _tracer_provider:
        try:
            _tracer_provider.shutdown()
            logger.info("OpenTelemetry tracing shut down successfully")
        except Exception as e:
            logger.error(f"Error shutting down tracing: {e}")


@contextmanager
def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: Any = None
):
    """
    Context manager for creating trace spans

    Args:
        name: Span name (e.g., "agent_execution", "llm_generate")
        attributes: Optional span attributes
        kind: Span kind (INTERNAL, CLIENT, SERVER, PRODUCER, CONSUMER)

    Usage:
        ```python
        with trace_span("analyze_logs", {"log_count": 100}):
            # Your code here
            pass
        ```
    """
    tracer = get_tracer()

    # Default to INTERNAL only when the OTel API is actually importable.
    if kind is None and TRACING_AVAILABLE:
        kind = trace.SpanKind.INTERNAL

    span_cm = (
        tracer.start_as_current_span(name, kind=kind) if kind is not None
        else tracer.start_as_current_span(name)
    )

    with span_cm as span:
        # Add attributes if provided
        if attributes:
            for key, value in attributes.items():
                # Convert non-primitive types to strings
                if isinstance(value, (list, dict)):
                    span.set_attribute(key, str(value))
                elif value is not None:
                    span.set_attribute(key, value)

        try:
            yield span
        except Exception as e:
            # Record exception in span
            span.record_exception(e)
            if TRACING_AVAILABLE:
                span.set_status(Status(StatusCode.ERROR, str(e)))
            raise


def trace_async_function(
    span_name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
):
    """
    Decorator for tracing async functions

    Args:
        span_name: Optional custom span name (defaults to function name)
        attributes: Optional span attributes

    Usage:
        ```python
        @trace_async_function(attributes={"component": "log_analyzer"})
        async def analyze_logs(logs):
            # Your code here
            pass
        ```
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            name = span_name or f"{func.__module__}.{func.__name__}"

            with trace_span(name, attributes):
                return await func(*args, **kwargs)

        return wrapper
    return decorator


def trace_function(
    span_name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
):
    """
    Decorator for tracing synchronous functions

    Args:
        span_name: Optional custom span name (defaults to function name)
        attributes: Optional span attributes
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = span_name or f"{func.__module__}.{func.__name__}"

            with trace_span(name, attributes):
                return func(*args, **kwargs)

        return wrapper
    return decorator


def add_span_attributes(attributes: Dict[str, Any]):
    """
    Add attributes to the current active span

    Args:
        attributes: Dictionary of attributes to add
    """
    if not TRACING_AVAILABLE:
        return

    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        for key, value in attributes.items():
            if isinstance(value, (list, dict)):
                current_span.set_attribute(key, str(value))
            elif value is not None:
                current_span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Add an event to the current active span

    Args:
        name: Event name
        attributes: Optional event attributes
    """
    if not TRACING_AVAILABLE:
        return

    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.add_event(name, attributes=attributes or {})


def set_span_error(error: Exception):
    """
    Mark current span as error and record exception

    Args:
        error: Exception to record
    """
    if not TRACING_AVAILABLE:
        return

    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.record_exception(error)
        current_span.set_status(Status(StatusCode.ERROR, str(error)))


def inject_trace_context(carrier: Dict[str, str]) -> Dict[str, str]:
    """
    Inject trace context into a carrier (e.g., HTTP headers)

    Args:
        carrier: Dictionary to inject context into

    Returns:
        Carrier with injected trace context
    """
    if not TRACING_AVAILABLE:
        return carrier

    propagator = TraceContextTextMapPropagator()
    propagator.inject(carrier)
    return carrier


def extract_trace_context(carrier: Dict[str, str]):
    """
    Extract trace context from a carrier (e.g., HTTP headers)

    Args:
        carrier: Dictionary containing trace context

    Returns:
        Extracted context
    """
    if not TRACING_AVAILABLE:
        return None

    propagator = TraceContextTextMapPropagator()
    return propagator.extract(carrier)


class TracingConfig:
    """Configuration for tracing"""

    def __init__(self):
        from config.settings import get_settings
        settings = get_settings()

        self.enabled = settings.enable_tracing
        self.otlp_endpoint = settings.otel_endpoint
        self.service_name = settings.otel_service_name

    def is_enabled(self) -> bool:
        """Check if tracing is enabled"""
        return self.enabled and self.otlp_endpoint is not None

