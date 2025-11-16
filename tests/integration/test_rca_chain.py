"""
Integration tests for complete RCA chain
"""
import pytest
from chains.orchestrator import AgentOrchestrator
from examples.synthetic_data import create_memory_leak_incident, create_database_pool_incident
from schemas import AgentStatus


class TestRCAChain:
    """Integration tests for RCA chain execution"""

    @pytest.mark.integration
    def test_memory_leak_scenario_end_to_end(self):
        """Test complete RCA chain with memory leak scenario"""
        orchestrator = AgentOrchestrator(error_strategy="continue")
        incident_data = create_memory_leak_incident()

        results = orchestrator.execute_rca_chain(incident_data)

        # Verify chain completed
        assert results["execution_summary"]["status"] == "completed"
        assert results["execution_summary"]["phases_completed"] == 3

        # Verify Phase 1 (diagnostic analysis)
        phase1 = results["phase1_analysis"]
        assert "log_analysis" in phase1
        assert "metrics_analysis" in phase1
        assert "change_correlation" in phase1
        assert "topology" in phase1

        # At least some agents should succeed
        successful = [
            r for r in phase1.values()
            if r and r.status == AgentStatus.COMPLETED
        ]
        assert len(successful) >= 2

        # Verify Phase 2 (hypothesis generation)
        phase2 = results["phase2_hypothesis"]
        if phase2 and phase2.status == AgentStatus.COMPLETED:
            assert len(phase2.findings) > 0
            top_hypothesis = phase2.findings[0]

            # Should mention memory or deployment
            description_lower = top_hypothesis.description.lower()
            assert "memory" in description_lower or \
                   "deployment" in description_lower or \
                   "oom" in description_lower

            # Should have high score
            assert top_hypothesis.metadata.get("hypothesis_score", 0) >= 60

        # Verify Phase 3 (remediation)
        phase3 = results["phase3_remediation"]
        if phase3 and phase3.status == AgentStatus.COMPLETED:
            assert len(phase3.findings) > 0

            # Should have immediate plan
            immediate_plans = [
                p for p in phase3.findings
                if p.metadata.get("plan_type") == "immediate"
            ]
            assert len(immediate_plans) > 0

            # Immediate plan should suggest rollback or restart
            plan_desc = immediate_plans[0].description.lower()
            assert "rollback" in plan_desc or \
                   "restart" in plan_desc or \
                   "scale" in plan_desc

    @pytest.mark.integration
    def test_database_pool_scenario(self):
        """Test RCA chain with database pool exhaustion"""
        orchestrator = AgentOrchestrator(error_strategy="continue")
        incident_data = create_database_pool_incident()

        results = orchestrator.execute_rca_chain(incident_data)

        assert results["execution_summary"]["status"] == "completed"

        # Should identify database/config issue
        if results["phase2_hypothesis"] and \
           results["phase2_hypothesis"].status == AgentStatus.COMPLETED:
            hypotheses = results["phase2_hypothesis"].findings
            if hypotheses:
                top_desc = hypotheses[0].description.lower()
                assert "database" in top_desc or \
                       "connection" in top_desc or \
                       "pool" in top_desc or \
                       "config" in top_desc

    @pytest.mark.integration
    def test_partial_failure_handling(self):
        """Test chain handles partial agent failures"""
        orchestrator = AgentOrchestrator(error_strategy="continue")

        # Create incident with minimal data (may cause some agents to fail)
        minimal_incident = {
            "description": "Test incident",
            "incident_time": "2024-01-15T14:23:00Z",
            "affected_services": ["test-service"],
            "logs": [],
            "metrics": [],
            "changes": [],
            "traces": []
        }

        results = orchestrator.execute_rca_chain(minimal_incident)

        # Chain should complete even with failures
        assert results["execution_summary"]["status"] in ["completed", "failed"]

        # Some phase 1 agents might fail with empty data, but shouldn't crash
        phase1 = results["phase1_analysis"]
        assert phase1 is not None

    @pytest.mark.integration
    def test_execution_time_reasonable(self):
        """Test that RCA chain completes in reasonable time"""
        orchestrator = AgentOrchestrator()
        incident_data = create_memory_leak_incident()

        results = orchestrator.execute_rca_chain(incident_data)

        # Should complete within 10 seconds for synthetic data
        execution_time = results["execution_summary"]["execution_time_ms"]
        assert execution_time < 10000  # 10 seconds

    @pytest.mark.integration
    def test_agent_finding_consistency(self):
        """Test that agent findings are consistent across runs"""
        orchestrator = AgentOrchestrator()
        incident_data = create_memory_leak_incident()

        # Run twice
        results1 = orchestrator.execute_rca_chain(incident_data)
        results2 = orchestrator.execute_rca_chain(incident_data)

        # Should produce similar results
        phase1_1 = results1["phase1_analysis"]
        phase1_2 = results2["phase1_analysis"]

        # Same agents should succeed/fail
        for agent_key in ["log_analysis", "metrics_analysis"]:
            if agent_key in phase1_1 and agent_key in phase1_2:
                assert phase1_1[agent_key].status == phase1_2[agent_key].status
