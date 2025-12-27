"""
Unit tests for RemediationPlannerAgent
"""
import pytest
from agents.remediation_planner_agent import RemediationPlannerAgent
from schemas import BaseAgentInput, AgentStatus, ConfidenceLevel, Finding


class TestRemediationPlannerAgent:
    """Test suite for RemediationPlannerAgent"""

    def test_initialization(self):
        """Test agent initializes correctly"""
        agent = RemediationPlannerAgent()
        assert agent.name == "RemediationPlannerAgent"
        assert agent.capabilities.name == "RemediationPlannerAgent"

    def test_execute_with_hypotheses(self):
        """Test remediation plan generation from hypotheses"""
        agent = RemediationPlannerAgent()
        
        hypotheses = [
            Finding(
                type="hypothesis",
                description="Memory leak in payment service causing OOM errors",
                confidence=ConfidenceLevel.HIGH,
                evidence=[
                    "OutOfMemoryError pattern detected",
                    "Memory usage increased from 35% to 98%",
                    "Deployment correlated with incident"
                ],
                severity="CRITICAL",
                metadata={"root_cause_score": 0.95}
            )
        ]
        
        input_data = BaseAgentInput(
            context={
                "hypotheses": hypotheses,
                "incident_data": {
                    "affected_services": ["payment-service"],
                    "incident_time": "2024-01-15T14:23:00Z"
                },
                "capabilities": {
                    "can_restart": True,
                    "can_scale": True,
                    "can_rollback": True
                }
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        assert len(result.findings) > 0
        assert result.summary is not None
        
        # Check that remediation plans have proper structure
        for plan in result.findings:
            assert plan.description is not None
            assert len(plan.evidence) > 0  # Should have action steps

    def test_action_prioritization(self):
        """Test that remediation actions are prioritized correctly"""
        agent = RemediationPlannerAgent()
        
        critical_hypothesis = Finding(
            type="hypothesis",
            description="Critical database failure",
            confidence=ConfidenceLevel.HIGH,
            evidence=["Database connection pool exhausted"],
            severity="CRITICAL"
        )
        
        low_hypothesis = Finding(
            type="hypothesis",
            description="Minor logging issue",
            confidence=ConfidenceLevel.LOW,
            evidence=["Some log messages missing"],
            severity="LOW"
        )
        
        input_data = BaseAgentInput(
            context={
                "hypotheses": [critical_hypothesis, low_hypothesis],
                "incident_data": {"affected_services": ["database"]},
                "capabilities": {"can_restart": True}
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # Critical issues should be addressed first
        if len(result.findings) > 1:
            # First plan should address critical issue
            first_plan = result.findings[0]
            assert "critical" in first_plan.description.lower() or "database" in first_plan.description.lower()

    def test_plan_generation_different_failure_types(self):
        """Test plan generation for different types of failures"""
        agent = RemediationPlannerAgent()
        
        # Test memory issue
        memory_hypothesis = Finding(
            type="hypothesis",
            description="Memory exhaustion",
            confidence=ConfidenceLevel.HIGH,
            evidence=["Memory spike"],
            severity="HIGH"
        )
        
        input_data = BaseAgentInput(
            context={
                "hypotheses": [memory_hypothesis],
                "incident_data": {"affected_services": ["service-1"]},
                "capabilities": {"can_restart": True, "can_scale": True}
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        assert len(result.findings) > 0
        # Should suggest memory-related remediation
        plan_text = " ".join([f.description for f in result.findings]).lower()
        assert any(keyword in plan_text for keyword in ["memory", "restart", "scale", "heap"])

    def test_capability_constraints(self):
        """Test that plans respect capability constraints"""
        agent = RemediationPlannerAgent()
        
        hypothesis = Finding(
            type="hypothesis",
            description="Service needs restart",
            confidence=ConfidenceLevel.HIGH,
            evidence=["Service hung"],
            severity="HIGH"
        )
        
        # Test with no restart capability
        input_data = BaseAgentInput(
            context={
                "hypotheses": [hypothesis],
                "incident_data": {"affected_services": ["service-1"]},
                "capabilities": {
                    "can_restart": False,
                    "can_scale": False,
                    "can_rollback": False
                }
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # Should still provide plans but with manual steps
        assert len(result.findings) > 0

    def test_rollback_recommendation(self):
        """Test rollback is recommended for deployment-related issues"""
        agent = RemediationPlannerAgent()
        
        deployment_hypothesis = Finding(
            type="hypothesis",
            description="Recent deployment introduced bug",
            confidence=ConfidenceLevel.HIGH,
            evidence=["Deployment correlated with errors"],
            severity="HIGH",
            metadata={"change_type": "deployment"}
        )
        
        input_data = BaseAgentInput(
            context={
                "hypotheses": [deployment_hypothesis],
                "incident_data": {"affected_services": ["app-service"]},
                "capabilities": {"can_rollback": True}
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # Should recommend rollback
        plan_text = " ".join([f.description for f in result.findings]).lower()
        assert "rollback" in plan_text or "revert" in plan_text

    def test_no_hypotheses(self):
        """Test handling when no hypotheses provided"""
        agent = RemediationPlannerAgent()
        
        input_data = BaseAgentInput(
            context={
                "hypotheses": [],
                "incident_data": {}
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # Should provide general investigation steps
        assert result.summary is not None

    def test_multiple_services_affected(self):
        """Test remediation when multiple services affected"""
        agent = RemediationPlannerAgent()
        
        hypothesis = Finding(
            type="hypothesis",
            description="Cascading failure across services",
            confidence=ConfidenceLevel.HIGH,
            evidence=["Multiple services failing"],
            severity="CRITICAL"
        )
        
        input_data = BaseAgentInput(
            context={
                "hypotheses": [hypothesis],
                "incident_data": {
                    "affected_services": ["service-1", "service-2", "service-3"]
                },
                "capabilities": {"can_restart": True}
            }
        )

        result = agent.execute(input_data)

        assert result.status == AgentStatus.COMPLETED
        # Should address multiple services
        assert len(result.findings) > 0

