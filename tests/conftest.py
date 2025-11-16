"""
Pytest configuration and fixtures
"""
import pytest
import sys
import os
from datetime import datetime
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas import BaseAgentInput, Finding, ConfidenceLevel


@pytest.fixture
def sample_logs() -> List[Dict]:
    """Sample log data for testing"""
    return [
        {
            "timestamp": "2024-01-15T14:23:00Z",
            "level": "ERROR",
            "service": "payment-service",
            "message": "OutOfMemoryError: Java heap space",
            "trace_id": "trace-001"
        },
        {
            "timestamp": "2024-01-15T14:23:01Z",
            "level": "ERROR",
            "service": "payment-service",
            "message": "OutOfMemoryError: Java heap space",
            "trace_id": "trace-002"
        },
        {
            "timestamp": "2024-01-15T14:23:02Z",
            "level": "ERROR",
            "service": "payment-service",
            "message": "OutOfMemoryError: Java heap space",
            "trace_id": "trace-003"
        },
        {
            "timestamp": "2024-01-15T14:23:30Z",
            "level": "ERROR",
            "service": "api-gateway",
            "message": "Timeout calling payment-service",
            "trace_id": "trace-004"
        },
        {
            "timestamp": "2024-01-15T14:20:00Z",
            "level": "INFO",
            "service": "payment-service",
            "message": "Processing payment",
            "trace_id": "trace-005"
        }
    ]


@pytest.fixture
def sample_metrics() -> List[Dict]:
    """Sample metrics data for testing"""
    return [
        {
            "name": "cpu_usage",
            "service": "payment-service",
            "timestamps": [
                "2024-01-15T14:20:00Z",
                "2024-01-15T14:21:00Z",
                "2024-01-15T14:22:00Z",
                "2024-01-15T14:23:00Z"
            ],
            "values": [35, 36, 37, 98],
            "unit": "percentage"
        },
        {
            "name": "memory_usage",
            "service": "payment-service",
            "timestamps": [
                "2024-01-15T14:20:00Z",
                "2024-01-15T14:21:00Z",
                "2024-01-15T14:22:00Z",
                "2024-01-15T14:23:00Z"
            ],
            "values": [35, 45, 75, 98],
            "unit": "percentage"
        }
    ]


@pytest.fixture
def sample_changes() -> List[Dict]:
    """Sample change events for testing"""
    return [
        {
            "id": "deploy-001",
            "type": "deployment",
            "timestamp": "2024-01-15T14:15:00Z",
            "service": "payment-service",
            "description": "Deployed v2.4.1",
            "author": "deploy-bot",
            "metadata": {
                "version": "v2.4.1",
                "previous_version": "v2.4.0"
            }
        }
    ]


@pytest.fixture
def sample_traces() -> List[Dict]:
    """Sample distributed traces for testing"""
    return [
        {
            "trace_id": "trace-001",
            "spans": [
                {
                    "span_id": "span-1",
                    "service": "api-gateway",
                    "operation": "handle_request",
                    "parent_id": None,
                    "duration_ms": 250
                },
                {
                    "span_id": "span-2",
                    "service": "payment-service",
                    "operation": "process_payment",
                    "parent_id": "span-1",
                    "duration_ms": 200
                }
            ]
        }
    ]


@pytest.fixture
def incident_time() -> str:
    """Sample incident timestamp"""
    return "2024-01-15T14:23:00Z"


@pytest.fixture
def affected_services() -> List[str]:
    """Sample affected services"""
    return ["payment-service"]


@pytest.fixture
def base_agent_input(sample_logs, incident_time) -> BaseAgentInput:
    """Base agent input fixture"""
    return BaseAgentInput(
        context={
            "logs": sample_logs,
            "incident_time": incident_time
        },
        parameters={}
    )


@pytest.fixture
def sample_finding() -> Finding:
    """Sample finding for testing"""
    return Finding(
        type="error_pattern",
        description="OutOfMemoryError pattern detected",
        confidence=ConfidenceLevel.HIGH,
        evidence=["Evidence 1", "Evidence 2"],
        severity="CRITICAL",
        metadata={
            "error_count": 3,
            "service": "payment-service"
        }
    )
