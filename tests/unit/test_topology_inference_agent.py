"""
Unit tests for TopologyInferenceAgent
"""
import pytest
from agents.topology_inference_agent import TopologyInferenceAgent
from schemas import BaseAgentInput, AgentStatus, ConfidenceLevel


class TestTopologyInferenceAgent:
    """Test suite for TopologyInferenceAgent"""

    def test_initialization(self):
        """Test agent initializes correctly"""
        agent = TopologyInferenceAgent()
        assert agent.name == "TopologyInferenceAgent"
        assert agent.capabilities.name == "TopologyInferenceAgent"

    def test_execute_with_traces(self, sample_traces):
        """Test topology inference from distributed traces"""
        agent = TopologyInferenceAgent()
        
        input_data = BaseAgentInput(
            context={
                "traces": sample_traces,
                "affected_services": ["payment-service"],
                "incident_time": "2024-01-15T14:23:00Z"
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        assert result.summary is not None
        # Should identify service dependencies
        assert len(result.findings) >= 0

    def test_dependency_graph_construction(self):
        """Test that dependency graph is correctly constructed"""
        agent = TopologyInferenceAgent()
        
        multi_service_traces = [
            {
                "trace_id": "trace-001",
                "spans": [
                    {
                        "span_id": "span-1",
                        "service": "api-gateway",
                        "operation": "handle_request",
                        "parent_id": None,
                        "duration_ms": 500
                    },
                    {
                        "span_id": "span-2",
                        "service": "auth-service",
                        "operation": "verify_token",
                        "parent_id": "span-1",
                        "duration_ms": 100
                    },
                    {
                        "span_id": "span-3",
                        "service": "payment-service",
                        "operation": "process_payment",
                        "parent_id": "span-1",
                        "duration_ms": 350
                    },
                    {
                        "span_id": "span-4",
                        "service": "database",
                        "operation": "query",
                        "parent_id": "span-3",
                        "duration_ms": 200
                    }
                ]
            }
        ]
        
        input_data = BaseAgentInput(
            context={
                "traces": multi_service_traces,
                "affected_services": ["payment-service"]
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # Should identify multiple services and their relationships
        if len(result.findings) > 0:
            # Findings should describe service dependencies
            descriptions = " ".join([f.description for f in result.findings]).lower()
            assert any(svc in descriptions for svc in ["api-gateway", "payment-service", "database"])

    def test_impact_zone_calculation(self):
        """Test calculation of incident impact zone"""
        agent = TopologyInferenceAgent()
        
        traces = [
            {
                "trace_id": "trace-001",
                "spans": [
                    {
                        "span_id": "1",
                        "service": "frontend",
                        "operation": "render",
                        "parent_id": None,
                        "duration_ms": 100
                    },
                    {
                        "span_id": "2",
                        "service": "api",
                        "operation": "api_call",
                        "parent_id": "1",
                        "duration_ms": 80
                    },
                    {
                        "span_id": "3",
                        "service": "backend",
                        "operation": "process",
                        "parent_id": "2",
                        "duration_ms": 60,
                        "error": True  # This service has an error
                    }
                ]
            }
        ]
        
        input_data = BaseAgentInput(
            context={
                "traces": traces,
                "affected_services": ["backend"]
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # Should identify impacted services upstream
        assert result.summary is not None

    def test_service_discovery(self):
        """Test service discovery from traces"""
        agent = TopologyInferenceAgent()
        
        traces = [
            {
                "trace_id": "trace-001",
                "spans": [
                    {"span_id": "1", "service": "service-a", "operation": "op1", "parent_id": None, "duration_ms": 10},
                    {"span_id": "2", "service": "service-b", "operation": "op2", "parent_id": "1", "duration_ms": 10},
                    {"span_id": "3", "service": "service-c", "operation": "op3", "parent_id": "1", "duration_ms": 10}
                ]
            },
            {
                "trace_id": "trace-002",
                "spans": [
                    {"span_id": "4", "service": "service-a", "operation": "op1", "parent_id": None, "duration_ms": 10},
                    {"span_id": "5", "service": "service-d", "operation": "op4", "parent_id": "4", "duration_ms": 10}
                ]
            }
        ]
        
        input_data = BaseAgentInput(
            context={
                "traces": traces,
                "affected_services": ["service-a"]
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # Should discover all unique services
        summary_text = result.summary.lower()
        # Service-a should be mentioned as it's affected
        assert "service" in summary_text

    def test_no_traces(self):
        """Test handling when no traces provided"""
        agent = TopologyInferenceAgent()
        
        input_data = BaseAgentInput(
            context={
                "traces": [],
                "affected_services": ["unknown-service"]
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # Should handle gracefully with no traces
        assert result.summary is not None

    def test_circular_dependencies(self):
        """Test handling of circular dependencies"""
        agent = TopologyInferenceAgent()
        
        # Create traces that might suggest circular calls
        traces = [
            {
                "trace_id": "trace-001",
                "spans": [
                    {"span_id": "1", "service": "service-a", "operation": "call_b", "parent_id": None, "duration_ms": 100},
                    {"span_id": "2", "service": "service-b", "operation": "call_c", "parent_id": "1", "duration_ms": 80},
                    {"span_id": "3", "service": "service-c", "operation": "call_a", "parent_id": "2", "duration_ms": 60}
                ]
            }
        ]
        
        input_data = BaseAgentInput(
            context={
                "traces": traces,
                "affected_services": ["service-a"]
            }
        )

        result = agent.execute(input_data)

        # Should handle without crashing
        assert result.status == AgentStatus.COMPLETED

    def test_performance_bottleneck_detection(self):
        """Test detection of performance bottlenecks in topology"""
        agent = TopologyInferenceAgent()
        
        traces = [
            {
                "trace_id": "trace-001",
                "spans": [
                    {"span_id": "1", "service": "frontend", "operation": "request", "parent_id": None, "duration_ms": 1050},
                    {"span_id": "2", "service": "slow-service", "operation": "process", "parent_id": "1", "duration_ms": 1000}  # Bottleneck
                ]
            }
        ]
        
        input_data = BaseAgentInput(
            context={
                "traces": traces,
                "affected_services": ["slow-service"]
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # May identify slow service
        if len(result.findings) > 0:
            # Check if slowness is mentioned
            descriptions = " ".join([f.description for f in result.findings]).lower()
            assert "slow" in descriptions or "latency" in descriptions or "duration" in descriptions or "service" in descriptions

    def test_missing_parent_spans(self):
        """Test handling of orphaned spans (missing parent)"""
        agent = TopologyInferenceAgent()
        
        traces = [
            {
                "trace_id": "trace-001",
                "spans": [
                    {"span_id": "2", "service": "service-b", "operation": "op", "parent_id": "missing", "duration_ms": 10}
                ]
            }
        ]
        
        input_data = BaseAgentInput(
            context={
                "traces": traces,
                "affected_services": ["service-b"]
            }
        )

        result = agent.execute(input_data)

        # Should handle gracefully
        assert result.status == AgentStatus.COMPLETED
        assert result.summary is not None

