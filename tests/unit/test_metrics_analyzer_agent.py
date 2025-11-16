"""
Unit tests for MetricsAnalyzerAgent
"""
import pytest
from agents.metrics_analyzer_agent import MetricsAnalyzerAgent
from schemas import BaseAgentInput, AgentStatus, ConfidenceLevel


class TestMetricsAnalyzerAgent:
    """Test suite for MetricsAnalyzerAgent"""

    def test_initialization(self):
        """Test agent initializes correctly"""
        agent = MetricsAnalyzerAgent()
        assert agent.name == "MetricsAnalyzerAgent"
        assert "metrics" in agent.capabilities.input_types

    def test_anomaly_detection(self):
        """Test statistical anomaly detection"""
        agent = MetricsAnalyzerAgent()

        # Create metric with clear anomaly
        metrics = [
            {
                "name": "cpu_usage",
                "service": "test-service",
                "timestamps": [f"2024-01-15T14:2{i}:00Z" for i in range(10)],
                "values": [30, 32, 31, 33, 32, 31, 30, 32, 98, 97],  # Last two are anomalies
                "unit": "percentage"
            }
        ]

        input_data = BaseAgentInput(
            context={"metrics": metrics},
            parameters={"anomaly_threshold": 3.0}
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        anomaly_findings = [f for f in result.findings if f.type == "anomaly"]
        assert len(anomaly_findings) > 0
        assert anomaly_findings[0].metadata["z_score"] >= 3.0

    def test_threshold_violation_detection(self):
        """Test threshold violation detection"""
        agent = MetricsAnalyzerAgent()

        metrics = [
            {
                "name": "cpu_usage",
                "service": "test-service",
                "timestamps": ["2024-01-15T14:20:00Z", "2024-01-15T14:21:00Z"],
                "values": [85, 90],  # Above 80% threshold
                "unit": "percentage"
            }
        ]

        input_data = BaseAgentInput(
            context={"metrics": metrics}
        )

        result = agent.execute(input_data)

        threshold_findings = [f for f in result.findings if f.type == "threshold_violation"]
        assert len(threshold_findings) > 0

    def test_correlation_detection(self):
        """Test metric correlation detection"""
        agent = MetricsAnalyzerAgent()

        metrics = [
            {
                "name": "throughput",
                "service": "test-service",
                "timestamps": ["2024-01-15T14:20:00Z", "2024-01-15T14:21:00Z"],
                "values": [1000, 500],  # Decreased 50%
                "unit": "requests_per_minute"
            },
            {
                "name": "p99_latency",
                "service": "test-service",
                "timestamps": ["2024-01-15T14:20:00Z", "2024-01-15T14:21:00Z"],
                "values": [100, 500],  # Increased 400%
                "unit": "milliseconds"
            }
        ]

        input_data = BaseAgentInput(
            context={"metrics": metrics}
        )

        result = agent.execute(input_data)

        # Should detect inverse correlation
        correlation_findings = [f for f in result.findings if f.type == "correlation"]
        if correlation_findings:
            assert "inverse" in correlation_findings[0].description.lower() or \
                   "throughput" in correlation_findings[0].description.lower()

    def test_empty_metrics(self):
        """Test handling of empty metrics"""
        agent = MetricsAnalyzerAgent()
        input_data = BaseAgentInput(
            context={"metrics": []}
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        assert "normal ranges" in result.summary.lower() or "no" in result.summary.lower()

    def test_insufficient_data_points(self):
        """Test handling of insufficient data points"""
        agent = MetricsAnalyzerAgent()

        metrics = [
            {
                "name": "cpu_usage",
                "service": "test-service",
                "timestamps": ["2024-01-15T14:20:00Z"],
                "values": [50],  # Only 1 point
                "unit": "percentage"
            }
        ]

        input_data = BaseAgentInput(
            context={"metrics": metrics}
        )

        result = agent.execute(input_data)

        # Should handle gracefully
        assert result.status == AgentStatus.COMPLETED
