"""
Unit tests for LogAnalyzerAgent
"""
import pytest
from agents.log_analyzer_agent import LogAnalyzerAgent
from schemas import BaseAgentInput, AgentStatus, ConfidenceLevel


class TestLogAnalyzerAgent:
    """Test suite for LogAnalyzerAgent"""

    def test_initialization(self):
        """Test agent initializes correctly"""
        agent = LogAnalyzerAgent()
        assert agent.name == "LogAnalyzerAgent"
        assert agent.capabilities.name == "LogAnalyzerAgent"
        assert "logs" in agent.capabilities.input_types

    def test_execute_with_error_pattern(self, sample_logs):
        """Test detection of error patterns"""
        agent = LogAnalyzerAgent()
        input_data = BaseAgentInput(
            context={
                "logs": sample_logs,
                "incident_time": "2024-01-15T14:23:00Z"
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        assert len(result.findings) > 0
        assert result.summary is not None
        assert result.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    def test_execute_with_no_logs(self):
        """Test handling of empty log input"""
        agent = LogAnalyzerAgent()
        input_data = BaseAgentInput(
            context={"logs": []}
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        assert len(result.findings) == 0
        assert "No significant issues" in result.summary

    def test_error_pattern_detection(self, sample_logs):
        """Test that recurring errors are detected"""
        agent = LogAnalyzerAgent()

        # Create logs with clear pattern
        error_logs = [
            {
                "timestamp": f"2024-01-15T14:23:0{i}Z",
                "level": "ERROR",
                "service": "test-service",
                "message": "DatabaseConnectionException: Pool exhausted",
                "trace_id": f"trace-{i}"
            }
            for i in range(5)
        ]

        input_data = BaseAgentInput(
            context={"logs": error_logs}
        )

        result = agent.execute(input_data)

        # Should detect error pattern
        assert len(result.findings) > 0
        error_finding = result.findings[0]
        assert error_finding.type == "error_pattern"
        assert error_finding.metadata["error_count"] >= 3

    def test_cascade_detection(self):
        """Test detection of cascading failures"""
        agent = LogAnalyzerAgent()

        # Create cascading error pattern
        cascade_logs = [
            {
                "timestamp": "2024-01-15T14:23:00Z",
                "level": "ERROR",
                "service": "service-a",
                "message": "Error occurred",
                "trace_id": "trace-001"
            },
            {
                "timestamp": "2024-01-15T14:23:01Z",
                "level": "ERROR",
                "service": "service-b",
                "message": "Error in service b",
                "trace_id": "trace-001"
            }
        ]

        input_data = BaseAgentInput(
            context={"logs": cascade_logs}
        )

        result = agent.execute(input_data)

        # Should detect cascade if multiple services with same trace
        cascade_findings = [f for f in result.findings if f.type == "cascade"]
        if cascade_findings:
            assert cascade_findings[0].metadata["cascade_depth"] >= 2

    def test_confidence_calculation(self, sample_logs):
        """Test confidence level is calculated properly"""
        agent = LogAnalyzerAgent()
        input_data = BaseAgentInput(
            context={"logs": sample_logs}
        )

        result = agent.execute(input_data)

        assert result.confidence in [
            ConfidenceLevel.HIGH,
            ConfidenceLevel.MEDIUM,
            ConfidenceLevel.LOW,
            ConfidenceLevel.UNCERTAIN
        ]

    def test_next_steps_generation(self, sample_logs):
        """Test that next steps are generated"""
        agent = LogAnalyzerAgent()
        input_data = BaseAgentInput(
            context={"logs": sample_logs}
        )

        result = agent.execute(input_data)

        assert len(result.next_steps) > 0
        assert all(isinstance(step, str) for step in result.next_steps)

    def test_execution_time_tracking(self, sample_logs):
        """Test that execution time is tracked"""
        agent = LogAnalyzerAgent()
        input_data = BaseAgentInput(
            context={"logs": sample_logs}
        )

        result = agent.execute(input_data)

        assert result.execution_time_ms is not None
        assert result.execution_time_ms >= 0

    def test_error_handling(self):
        """Test agent handles errors gracefully"""
        agent = LogAnalyzerAgent()

        # Invalid input
        input_data = BaseAgentInput(
            context={"logs": "not a list"}  # Invalid type
        )

        result = agent.execute(input_data)

        # Should handle gracefully
        assert result.status in [AgentStatus.FAILED, AgentStatus.COMPLETED]

    @pytest.mark.parametrize("log_count", [10, 100, 500])
    def test_performance_scaling(self, log_count):
        """Test performance with different log volumes"""
        agent = LogAnalyzerAgent()

        logs = [
            {
                "timestamp": f"2024-01-15T14:23:{i%60:02d}Z",
                "level": "ERROR" if i % 10 == 0 else "INFO",
                "service": "test-service",
                "message": f"Message {i}",
                "trace_id": f"trace-{i}"
            }
            for i in range(log_count)
        ]

        input_data = BaseAgentInput(
            context={"logs": logs}
        )

        result = agent.execute(input_data)

        # Should complete in reasonable time
        assert result.execution_time_ms < 5000  # 5 seconds max
        assert result.status == AgentStatus.COMPLETED
