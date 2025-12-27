"""
Unit tests for HypothesisGeneratorAgent
"""
import pytest
from agents.hypothesis_generator_agent import HypothesisGeneratorAgent
from schemas import BaseAgentInput, AgentStatus, ConfidenceLevel, Finding


class TestHypothesisGeneratorAgent:
    """Test suite for HypothesisGeneratorAgent"""

    def test_initialization(self):
        """Test agent initializes correctly"""
        agent = HypothesisGeneratorAgent()
        assert agent.name == "HypothesisGeneratorAgent"
        assert agent.capabilities.name == "HypothesisGeneratorAgent"

    def test_execute_with_multiple_findings(self, sample_finding):
        """Test hypothesis generation from multiple agent findings"""
        agent = HypothesisGeneratorAgent()
        
        # Simulate findings from multiple agents
        findings_from_agents = {
            "log_analyzer": [sample_finding],
            "metrics_analyzer": [
                Finding(
                    type="anomaly",
                    description="Memory spike detected",
                    confidence=ConfidenceLevel.HIGH,
                    evidence=["Memory usage increased from 35% to 98%"],
                    severity="HIGH"
                )
            ],
            "change_correlator": [
                Finding(
                    type="correlation",
                    description="Deployment correlated with incident",
                    confidence=ConfidenceLevel.MEDIUM,
                    evidence=["Deployment occurred 8 minutes before incident"],
                    severity="MEDIUM"
                )
            ]
        }
        
        input_data = BaseAgentInput(
            context={
                "findings": findings_from_agents,
                "incident_time": "2024-01-15T14:23:00Z",
                "affected_services": ["payment-service"]
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        assert len(result.findings) > 0
        assert result.summary is not None
        # Hypotheses should have confidence scores
        for hypothesis in result.findings:
            assert hasattr(hypothesis, 'confidence')
            assert hypothesis.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    def test_execute_with_no_findings(self):
        """Test handling when no findings provided"""
        agent = HypothesisGeneratorAgent()
        input_data = BaseAgentInput(
            context={"findings": {}}
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        assert len(result.findings) == 0 or "insufficient evidence" in result.summary.lower()

    def test_hypothesis_scoring(self, sample_finding):
        """Test that hypotheses are scored based on evidence"""
        agent = HypothesisGeneratorAgent()
        
        # High evidence findings
        high_evidence_findings = {
            "log_analyzer": [sample_finding],
            "metrics_analyzer": [
                Finding(
                    type="anomaly",
                    description="Critical resource exhaustion",
                    confidence=ConfidenceLevel.HIGH,
                    evidence=["Evidence 1", "Evidence 2", "Evidence 3"],
                    severity="CRITICAL"
                )
            ]
        }
        
        input_data = BaseAgentInput(
            context={
                "findings": high_evidence_findings,
                "incident_time": "2024-01-15T14:23:00Z"
            }
        )

        result = agent.execute(input_data)

        # Should generate high-confidence hypotheses with strong evidence
        assert result.status == AgentStatus.COMPLETED
        if len(result.findings) > 0:
            # At least one hypothesis should have high confidence
            confidences = [f.confidence for f in result.findings]
            assert ConfidenceLevel.HIGH in confidences or ConfidenceLevel.MEDIUM in confidences

    def test_evidence_aggregation(self):
        """Test that evidence is aggregated from multiple sources"""
        agent = HypothesisGeneratorAgent()
        
        findings = {
            "log_analyzer": [
                Finding(
                    type="error",
                    description="Database connection errors",
                    confidence=ConfidenceLevel.HIGH,
                    evidence=["Connection pool exhausted"],
                    severity="HIGH"
                )
            ],
            "metrics_analyzer": [
                Finding(
                    type="anomaly",
                    description="Connection pool saturation",
                    confidence=ConfidenceLevel.HIGH,
                    evidence=["Active connections at maximum"],
                    severity="HIGH"
                )
            ]
        }
        
        input_data = BaseAgentInput(
            context={
                "findings": findings,
                "incident_time": "2024-01-15T14:23:00Z"
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # Should correlate related findings into hypotheses
        assert len(result.findings) > 0

    def test_missing_agent_results(self, sample_finding):
        """Test handling of missing results from some agents"""
        agent = HypothesisGeneratorAgent()
        
        # Only partial agent results
        findings = {
            "log_analyzer": [sample_finding],
            "metrics_analyzer": None,  # Missing
            "change_correlator": []     # Empty
        }
        
        input_data = BaseAgentInput(
            context={
                "findings": findings,
                "incident_time": "2024-01-15T14:23:00Z"
            }
        )

        result = agent.execute(input_data)

        # Should handle gracefully and work with available data
        assert result.status == AgentStatus.COMPLETED
        assert result.summary is not None

    def test_minimum_evidence_sources(self):
        """Test that hypotheses require minimum evidence sources"""
        agent = HypothesisGeneratorAgent()
        
        # Single source of evidence
        single_source = {
            "log_analyzer": [
                Finding(
                    type="error",
                    description="Single error",
                    confidence=ConfidenceLevel.LOW,
                    evidence=["One piece of evidence"],
                    severity="LOW"
                )
            ]
        }
        
        input_data = BaseAgentInput(
            context={
                "findings": single_source,
                "incident_time": "2024-01-15T14:23:00Z"
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # With minimal evidence, confidence should be lower
        if len(result.findings) > 0:
            for finding in result.findings:
                # Shouldn't generate HIGH confidence with single source
                assert finding.confidence in [ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN]

