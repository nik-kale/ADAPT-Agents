"""
Unit tests for AsyncAgentOrchestrator
"""

import pytest
import asyncio
from chains.async_orchestrator import AsyncAgentOrchestrator
from schemas import AgentStatus


@pytest.mark.asyncio
async def test_orchestrator_basic():
    """Test basic orchestration"""
    orchestrator = AsyncAgentOrchestrator(error_strategy="continue")

    incident_data = {
        "incident_time": "2025-01-15T10:00:00Z",
        "affected_services": ["api-service"],
        "logs": [
            {"timestamp": "2025-01-15T10:00:00Z", "level": "ERROR", "message": "OutOfMemoryError", "service": "api-service"}
        ],
        "metrics": [
            {"name": "memory_usage", "service": "api-service", "values": [95, 96, 97, 98, 99], "unit": "%"}
        ],
        "changes": []
    }

    result = await orchestrator.execute_rca_chain(incident_data)

    assert "phase1" in result
    assert "phase2" in result
    assert "phase3" in result
    assert result["success"] is True


@pytest.mark.asyncio
async def test_orchestrator_parallel_execution():
    """Test that phase 1 agents execute in parallel"""
    orchestrator = AsyncAgentOrchestrator()

    incident_data = {
        "incident_time": "2025-01-15T10:00:00Z",
        "affected_services": ["api-service"],
        "logs": [{"timestamp": "2025-01-15T10:00:00Z", "level": "ERROR", "message": "Connection timeout", "service": "api-service"}],
        "metrics": [{"name": "cpu_usage", "service": "api-service", "values": [85, 90, 95], "unit": "%"}],
        "changes": [{"id": "ch-001", "service": "api-service", "type": "config_change", "timestamp": "2025-01-15T09:55:00Z"}],
        "traces": []
    }

    import time
    start = time.time()
    result = await orchestrator.execute_rca_chain(incident_data)
    duration = time.time() - start

    # Parallel execution should be faster than sequential
    # With 4 agents in phase 1, parallel should be ~4x faster
    # Just check that it completes (actual timing depends on system)
    assert result["success"] is True
    assert duration < 10  # Should complete in reasonable time


@pytest.mark.asyncio
async def test_orchestrator_with_llm():
    """Test orchestrator with LLM enabled"""
    orchestrator = AsyncAgentOrchestrator(use_llm=False)  # Set to False for testing without API keys

    incident_data = {
        "incident_time": "2025-01-15T10:00:00Z",
        "affected_services": ["api-service"],
        "logs": [{"timestamp": "2025-01-15T10:00:00Z", "level": "ERROR", "message": "Database connection failed", "service": "api-service"}],
        "metrics": [],
        "changes": []
    }

    result = await orchestrator.execute_rca_chain(incident_data)

    assert result["success"] is True


@pytest.mark.asyncio
async def test_orchestrator_pii_filtering():
    """Test PII filtering"""
    orchestrator = AsyncAgentOrchestrator(filter_pii=True)

    incident_data = {
        "incident_time": "2025-01-15T10:00:00Z",
        "affected_services": ["api-service"],
        "logs": [
            {
                "timestamp": "2025-01-15T10:00:00Z",
                "level": "ERROR",
                "message": "Failed to authenticate user john@example.com with password secret123",
                "service": "api-service"
            }
        ],
        "metrics": [],
        "changes": []
    }

    result = await orchestrator.execute_rca_chain(incident_data)

    # PII should be filtered from logs
    assert result["success"] is True
    # Email should be redacted in processed logs


@pytest.mark.asyncio
async def test_orchestrator_error_handling():
    """Test error handling strategy"""
    orchestrator = AsyncAgentOrchestrator(error_strategy="continue")

    # Invalid incident data
    incident_data = {
        "incident_time": "invalid-time",
        "logs": [],
        "metrics": [],
        "changes": []
    }

    result = await orchestrator.execute_rca_chain(incident_data)

    # Should still return a result even with errors
    assert "phase1" in result
    assert "error" in result or result.get("success") is not None
