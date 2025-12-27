"""
OpenTelemetry Distributed Tracing

Provides trace instrumentation for analyzing request flows through
the agent pipeline with correlation across API requests and background jobs.
"""

import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager
from functools import wraps

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)

# Global tracer
_tracer: Optional[trace.Tracer] = None
_tracer_provider: Optional[TracerProvider] = None


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


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance"""
    global _tracer

    if _tracer is None:
        # Initialize with defaults if not already initialized
        init_tracing()

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
    kind: trace.SpanKind = trace.SpanKind.INTERNAL
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

    with tracer.start_as_current_span(name, kind=kind) as span:
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
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.add_event(name, attributes=attributes or {})


def set_span_error(error: Exception):
    """
    Mark current span as error and record exception

    Args:
        error: Exception to record
    """
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

