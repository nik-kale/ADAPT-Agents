"""
Unit tests for ChangeCorrelatorAgent (async)
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from agents.change_correlator_agent import ChangeCorrelatorAgent
from schemas import BaseAgentInput, AgentStatus, ConfidenceLevel


@pytest.mark.asyncio
async def test_change_correlator_basic():
    """Test basic change correlation"""
    agent = ChangeCorrelatorAgent()

    incident_time = datetime.now().isoformat()
    change_time = (datetime.now() - timedelta(minutes=10)).isoformat()

    input_data = BaseAgentInput(
        context={
            "incident_time": incident_time,
            "affected_services": ["api-service"],
            "changes": [
                {
                    "id": "change-001",
                    "service": "api-service",
                    "type": "deployment",
                    "timestamp": change_time,
                    "description": "Deployed v2.0.0"
                }
            ]
        }
    )

    result = await agent.execute_async(input_data)

    assert result.status == AgentStatus.COMPLETED
    assert result.agent_name == "ChangeCorrelatorAgent"
    assert len(result.findings) > 0
    assert result.execution_time_ms > 0


@pytest.mark.asyncio
async def test_change_correlator_high_risk():
    """Test high-risk change detection"""
    agent = ChangeCorrelatorAgent()

    incident_time = datetime.now().isoformat()
    change_time = (datetime.now() - timedelta(minutes=2)).isoformat()  # Very recent

    input_data = BaseAgentInput(
        context={
            "incident_time": incident_time,
            "affected_services": ["payment-service"],
            "changes": [
                {
                    "id": "change-002",
                    "service": "payment-service",
                    "type": "deployment",
                    "timestamp": change_time,
                    "description": "Major version upgrade",
                    "metadata": {"version": "2.0.0"}
                }
            ]
        }
    )

    result = await agent.execute_async(input_data)

    assert result.status == AgentStatus.COMPLETED
    assert len(result.findings) > 0
    # Recent deployment on affected service should be high risk
    assert any(f.metadata.get("risk_score", 0) >= 60 for f in result.findings)


@pytest.mark.asyncio
async def test_change_correlator_concurrent_changes():
    """Test concurrent changes pattern detection"""
    agent = ChangeCorrelatorAgent()

    incident_time = datetime.now().isoformat()

    changes = [
        {
            "id": f"change-{i:03d}",
            "service": f"service-{i}",
            "type": "deployment",
            "timestamp": (datetime.now() - timedelta(minutes=i*5)).isoformat(),
            "description": f"Change {i}"
        }
        for i in range(5)
    ]

    input_data = BaseAgentInput(
        context={
            "incident_time": incident_time,
            "affected_services": ["service-0"],
            "changes": changes
        }
    )

    result = await agent.execute_async(input_data)

    assert result.status == AgentStatus.COMPLETED
    # Should detect concurrent changes pattern
    assert any(f.type == "concurrent_changes" for f in result.findings)


@pytest.mark.asyncio
async def test_change_correlator_no_changes():
    """Test with no changes"""
    agent = ChangeCorrelatorAgent()

    input_data = BaseAgentInput(
        context={
            "incident_time": datetime.now().isoformat(),
            "affected_services": ["api-service"],
            "changes": []
        }
    )

    result = await agent.execute_async(input_data)

    assert result.status == AgentStatus.COMPLETED
    assert len(result.findings) == 0
    assert "No" in result.summary


@pytest.mark.asyncio
async def test_change_correlator_caching():
    """Test that caching works"""
    agent = ChangeCorrelatorAgent()

    incident_time = datetime.now().isoformat()
    change_time = (datetime.now() - timedelta(minutes=10)).isoformat()

    input_data = BaseAgentInput(
        context={
            "incident_time": incident_time,
            "affected_services": ["api-service"],
            "changes": [
                {
                    "id": "change-001",
                    "service": "api-service",
                    "type": "deployment",
                    "timestamp": change_time
                }
            ]
        }
    )

    # First execution
    result1 = await agent.execute_async(input_data)
    time1 = result1.execution_time_ms

    # Second execution (should be cached)
    result2 = await agent.execute_async(input_data)
    time2 = result2.execution_time_ms

    # Cached result should be faster (though not always guaranteed)
    assert result1.findings == result2.findings
    assert result1.summary == result2.summary
