"""
Prometheus metrics for agents
"""

from typing import Optional
from functools import wraps
import time


try:
    from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


# Define metrics if Prometheus available
if PROMETHEUS_AVAILABLE:
    # Counters
    agent_executions_total = Counter(
        'adapt_agent_executions_total',
        'Total agent executions',
        ['agent_name', 'status']
    )

    agent_findings_total = Counter(
        'adapt_agent_findings_total',
        'Total findings generated',
        ['agent_name', 'finding_type', 'severity']
    )

    # Histograms
    agent_execution_duration_seconds = Histogram(
        'adapt_agent_execution_duration_seconds',
        'Agent execution duration in seconds',
        ['agent_name'],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
    )

    hypothesis_scores = Histogram(
        'adapt_hypothesis_scores',
        'Hypothesis confidence scores',
        buckets=[0, 20, 40, 60, 80, 100]
    )

    # Gauges
    active_agent_executions = Gauge(
        'adapt_active_agent_executions',
        'Currently executing agents',
        ['agent_name']
    )

    cache_hits_total = Counter(
        'adapt_cache_hits_total',
        'Cache hits',
        ['agent_name']
    )

    cache_misses_total = Counter(
        'adapt_cache_misses_total',
        'Cache misses',
        ['agent_name']
    )

    # Info
    agent_info = Info(
        'adapt_agent',
        'Agent version and configuration'
    )


def record_execution_metrics(func):
    """Decorator to record agent execution metrics"""
    if not PROMETHEUS_AVAILABLE:
        return func

    @wraps(func)
    async def async_wrapper(self, input_data, *args, **kwargs):
        agent_name = getattr(self, 'name', 'unknown')
        active_agent_executions.labels(agent_name=agent_name).inc()
        start = time.time()

        try:
            result = await func(self, input_data, *args, **kwargs)

            # Record success
            duration = time.time() - start
            agent_executions_total.labels(
                agent_name=agent_name,
                status=result.status.value if hasattr(result.status, 'value') else str(result.status)
            ).inc()

            agent_execution_duration_seconds.labels(
                agent_name=agent_name
            ).observe(duration)

            # Record findings
            for finding in result.findings:
                agent_findings_total.labels(
                    agent_name=agent_name,
                    finding_type=finding.type,
                    severity=finding.severity or "NONE"
                ).inc()

                # Record hypothesis scores
                if finding.type == "hypothesis" and "hypothesis_score" in finding.metadata:
                    hypothesis_scores.observe(finding.metadata["hypothesis_score"])

            return result

        except Exception as e:
            agent_executions_total.labels(
                agent_name=agent_name,
                status="failed"
            ).inc()
            raise
        finally:
            active_agent_executions.labels(agent_name=agent_name).dec()

    @wraps(func)
    def sync_wrapper(self, input_data, *args, **kwargs):
        agent_name = getattr(self, 'name', 'unknown')
        active_agent_executions.labels(agent_name=agent_name).inc()
        start = time.time()

        try:
            result = func(self, input_data, *args, **kwargs)

            # Record metrics (same as async)
            duration = time.time() - start
            agent_executions_total.labels(
                agent_name=agent_name,
                status=result.status.value if hasattr(result.status, 'value') else str(result.status)
            ).inc()

            agent_execution_duration_seconds.labels(
                agent_name=agent_name
            ).observe(duration)

            for finding in result.findings:
                agent_findings_total.labels(
                    agent_name=agent_name,
                    finding_type=finding.type,
                    severity=finding.severity or "NONE"
                ).inc()

            return result

        except Exception as e:
            agent_executions_total.labels(
                agent_name=agent_name,
                status="failed"
            ).inc()
            raise
        finally:
            active_agent_executions.labels(agent_name=agent_name).dec()

    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def record_cache_hit(agent_name: str):
    """Record cache hit"""
    if PROMETHEUS_AVAILABLE:
        cache_hits_total.labels(agent_name=agent_name).inc()


def record_cache_miss(agent_name: str):
    """Record cache miss"""
    if PROMETHEUS_AVAILABLE:
        cache_misses_total.labels(agent_name=agent_name).inc()


def start_metrics_server(port: int = 9090):
    """Start Prometheus metrics server"""
    if PROMETHEUS_AVAILABLE:
        start_http_server(port)
        print(f"Metrics server started on port {port}")
    else:
        print("Prometheus client not installed. Metrics disabled.")
