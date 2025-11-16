"""
Synthetic Test Data Generator
Creates realistic incident data for testing ADAPT agents.
"""

from datetime import datetime, timedelta


def create_memory_leak_incident():
    """
    Create synthetic data for a memory leak incident caused by deployment.

    Scenario:
    - payment-service deployed v2.4.1 at 14:15:00
    - Memory usage started climbing at 14:17:00
    - OutOfMemoryErrors started at 14:23:00
    - Service became unresponsive
    """

    incident_time = "2024-01-15T14:23:00Z"
    base_time = datetime.fromisoformat("2024-01-15T14:00:00")

    # Generate synthetic logs
    logs = []

    # Normal logs before deployment
    for i in range(5):
        t = base_time + timedelta(minutes=i)
        logs.append({
            "timestamp": t.isoformat() + "Z",
            "level": "INFO",
            "service": "payment-service",
            "message": "Processing payment request",
            "trace_id": f"trace-{i}"
        })

    # Deployment log
    logs.append({
        "timestamp": "2024-01-15T14:15:00Z",
        "level": "INFO",
        "service": "payment-service",
        "message": "Deployment: Updated to version v2.4.1",
        "trace_id": "deploy-001"
    })

    # Warning signs
    logs.append({
        "timestamp": "2024-01-15T14:18:00Z",
        "level": "WARN",
        "service": "payment-service",
        "message": "GC overhead limit exceeded warning",
        "trace_id": "trace-100"
    })

    # Error burst
    for i in range(47):
        t = datetime.fromisoformat("2024-01-15T14:23:00") + timedelta(seconds=i*2)
        logs.append({
            "timestamp": t.isoformat() + "Z",
            "level": "ERROR",
            "service": "payment-service",
            "message": "OutOfMemoryError: Java heap space",
            "trace_id": f"trace-{200+i}"
        })

    # Cascading errors in dependent services
    logs.append({
        "timestamp": "2024-01-15T14:23:30Z",
        "level": "ERROR",
        "service": "api-gateway",
        "message": "Timeout calling payment-service after 30s",
        "trace_id": "trace-500"
    })

    # Generate synthetic metrics
    metrics = []

    # CPU usage (relatively stable)
    cpu_values = [35, 36, 37, 35, 38, 37, 36, 35, 37, 38,  # Before deployment
                  36, 37, 38, 39, 40, 42, 45, 48, 50, 52]  # After deployment
    cpu_timestamps = [
        (base_time + timedelta(minutes=i)).isoformat() + "Z"
        for i in range(20)
    ]
    metrics.append({
        "name": "cpu_usage",
        "service": "payment-service",
        "timestamps": cpu_timestamps,
        "values": cpu_values,
        "unit": "percentage"
    })

    # Memory usage (shows the leak)
    memory_values = [35, 36, 35, 37, 36, 35, 36, 35,  # Before deployment (stable)
                    38, 40, 45, 52, 61, 73, 85, 92, 97, 98, 98, 98]  # After (climbing)
    memory_timestamps = cpu_timestamps
    metrics.append({
        "name": "memory_usage",
        "service": "payment-service",
        "timestamps": memory_timestamps,
        "values": memory_values,
        "unit": "percentage"
    })

    # Error rate
    error_rate_values = [0.05, 0.04, 0.05, 0.05, 0.04, 0.05, 0.05, 0.04,  # Normal
                        0.05, 0.06, 0.08, 0.12, 0.18, 0.35, 0.67, 1.2, 2.5, 3.8, 4.2, 4.5]  # Spiking
    metrics.append({
        "name": "error_rate",
        "service": "payment-service",
        "timestamps": cpu_timestamps,
        "values": error_rate_values,
        "unit": "percentage"
    })

    # Throughput (degrading)
    throughput_values = [1000, 1020, 980, 1010, 990, 1005, 995, 1000,  # Stable
                        980, 950, 900, 820, 720, 580, 420, 280, 180, 120, 80, 50]  # Dropping
    metrics.append({
        "name": "throughput",
        "service": "payment-service",
        "timestamps": cpu_timestamps,
        "values": throughput_values,
        "unit": "requests_per_minute"
    })

    # P99 latency (increasing)
    latency_values = [150, 155, 148, 152, 151, 149, 153, 150,  # Normal
                     165, 185, 220, 280, 350, 480, 650, 820, 1100, 1400, 1800, 2200]  # Degrading
    metrics.append({
        "name": "p99_latency",
        "service": "payment-service",
        "timestamps": cpu_timestamps,
        "values": latency_values,
        "unit": "milliseconds"
    })

    # Generate change events
    changes = [
        {
            "id": "deploy-12345",
            "type": "deployment",
            "timestamp": "2024-01-15T14:15:00Z",
            "service": "payment-service",
            "description": "Deployed payment-service v2.4.1",
            "author": "deploy-bot",
            "metadata": {
                "version": "v2.4.1",
                "previous_version": "v2.4.0",
                "affected_components": ["payment-service"]
            }
        },
        {
            "id": "config-789",
            "type": "config_change",
            "timestamp": "2024-01-15T13:45:00Z",
            "service": "api-gateway",
            "description": "Updated rate limiting config",
            "author": "ops-team",
            "metadata": {
                "config_keys": ["rate_limit_requests_per_minute"],
                "old_value": "5000",
                "new_value": "10000"
            }
        }
    ]

    # Generate distributed traces (showing service dependencies)
    traces = [
        {
            "trace_id": "trace-001",
            "spans": [
                {
                    "span_id": "span-1",
                    "service": "api-gateway",
                    "operation": "handle_request",
                    "parent_id": None,
                    "duration_ms": 245
                },
                {
                    "span_id": "span-2",
                    "service": "payment-service",
                    "operation": "process_payment",
                    "parent_id": "span-1",
                    "duration_ms": 200
                },
                {
                    "span_id": "span-3",
                    "service": "payment-db",
                    "operation": "insert_transaction",
                    "parent_id": "span-2",
                    "duration_ms": 150
                }
            ]
        }
    ]

    return {
        "description": "Payment service experiencing OutOfMemoryErrors and degraded performance",
        "incident_time": incident_time,
        "affected_services": ["payment-service"],
        "logs": logs,
        "metrics": metrics,
        "changes": changes,
        "traces": traces,
        "time_range": {
            "start": "2024-01-15T14:00:00Z",
            "end": "2024-01-15T14:30:00Z"
        },
        "current_state": {
            "services_down": [],
            "services_degraded": ["payment-service"],
            "customer_impact": "Payment processing failures, high latency"
        },
        "capabilities": {
            "can_rollback": True,
            "can_scale": True,
            "can_restart": True,
            "manual_intervention_required": False
        },
        "parameters": {
            "suppress_reasoning": False,
            "max_hypotheses": 5
        }
    }


def create_database_pool_incident():
    """
    Create synthetic data for database connection pool exhaustion.

    Scenario:
    - Config change reduced pool size from 100 to 50
    - Under normal load, pool became exhausted
    - Connection errors started occurring
    """

    incident_time = "2024-01-15T14:23:00Z"

    logs = [
        {
            "timestamp": "2024-01-15T14:08:00Z",
            "level": "INFO",
            "service": "payment-service",
            "message": "Configuration reloaded: connection_pool_size=50",
            "trace_id": "config-001"
        }
    ]

    # Add connection errors
    for i in range(47):
        logs.append({
            "timestamp": f"2024-01-15T14:23:{i:02d}Z",
            "level": "ERROR",
            "service": "payment-service",
            "message": "DatabaseConnectionException: Connection pool exhausted. Active: 50, Idle: 0",
            "trace_id": f"trace-{i}"
        })

    metrics = [
        {
            "name": "db_connections_active",
            "service": "payment-service",
            "timestamps": ["2024-01-15T14:20:00Z", "2024-01-15T14:22:00Z", "2024-01-15T14:23:00Z"],
            "values": [45, 49, 50],
            "unit": "count"
        }
    ]

    changes = [
        {
            "id": "config-db-001",
            "type": "config_change",
            "timestamp": "2024-01-15T14:08:00Z",
            "service": "payment-service",
            "description": "Reduced database connection pool size",
            "author": "ops-team",
            "metadata": {
                "config_keys": ["connection_pool_size"],
                "old_value": "100",
                "new_value": "50"
            }
        }
    ]

    return {
        "description": "Database connection pool exhaustion",
        "incident_time": incident_time,
        "affected_services": ["payment-service"],
        "logs": logs,
        "metrics": metrics,
        "changes": changes,
        "traces": [],
        "current_state": {
            "services_degraded": ["payment-service"]
        },
        "capabilities": {
            "can_rollback": True,
            "can_scale": False,
            "can_restart": True
        }
    }


if __name__ == "__main__":
    # Test data generation
    print("Generating synthetic incident data...\n")

    incident = create_memory_leak_incident()
    print(f"Incident: {incident['description']}")
    print(f"Logs: {len(incident['logs'])}")
    print(f"Metrics: {len(incident['metrics'])}")
    print(f"Changes: {len(incident['changes'])}")
    print(f"Traces: {len(incident['traces'])}")
