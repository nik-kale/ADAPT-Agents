"""
Async Agent Chain Orchestrator
Coordinates execution of multiple diagnostic agents in parallel using async/await.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from schemas import BaseAgentInput, BaseAgentOutput, AgentStatus, ConfidenceLevel
from agents.log_analyzer_agent import LogAnalyzerAgent
from agents.metrics_analyzer_agent import MetricsAnalyzerAgent
from agents.change_correlator_agent import ChangeCorrelatorAgent
from agents.topology_inference_agent import TopologyInferenceAgent
from agents.hypothesis_generator_agent import HypothesisGeneratorAgent
from agents.remediation_planner_agent import RemediationPlannerAgent
from security.pii_filter import PIIFilter
from utils.logging import get_logger


class AsyncAgentOrchestrator:
    """
    Async orchestrator for diagnostic agents.

    Features:
    - Parallel execution of independent agents
    - Proper async/await throughout
    - PII filtering integration
    - Structured logging
    - Error handling with graceful degradation
    """

    def __init__(self, error_strategy: str = "continue", use_llm: bool = False,
                 filter_pii: bool = True):
        """
        Initialize async orchestrator.

        Args:
            error_strategy: How to handle agent failures
                           - "continue": Continue with partial results
                           - "fail_fast": Stop on first failure
                           - "best_effort": Try all agents, report what worked
            use_llm: Whether to use LLM-powered analysis
            filter_pii: Whether to filter PII from logs/data
        """
        self.error_strategy = error_strategy
        self.use_llm = use_llm
        self.filter_pii = filter_pii
        self.execution_history = []
        self.logger = get_logger(__name__)

        # Initialize PII filter
        if filter_pii:
            self.pii_filter = PIIFilter()
        else:
            self.pii_filter = None

        # Initialize agents
        self.log_analyzer = LogAnalyzerAgent(use_llm=use_llm)
        self.metrics_analyzer = MetricsAnalyzerAgent(use_llm=use_llm)
        self.change_correlator = ChangeCorrelatorAgent(use_llm=use_llm)
        self.topology_inference = TopologyInferenceAgent(use_llm=use_llm)
        self.hypothesis_generator = HypothesisGeneratorAgent(use_llm=use_llm)
        self.remediation_planner = RemediationPlannerAgent(use_llm=use_llm)

    async def execute_rca_chain(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute full async RCA chain: analysis → hypothesis → remediation.

        Args:
            incident_data: Dictionary containing:
                - logs: List of log entries
                - metrics: List of metrics
                - changes: List of change events
                - traces: List of distributed traces
                - incident_time: Timestamp of incident
                - affected_services: List of affected services

        Returns:
            Dictionary with results from each phase
        """
        start_time = datetime.now()
        self.logger.info("Starting async RCA chain", incident_time=incident_data.get("incident_time"))

        # Filter PII if enabled
        if self.pii_filter and "logs" in incident_data:
            incident_data["logs"] = self.pii_filter.filter_logs(incident_data["logs"])
            self.logger.info("PII filtered from logs", log_count=len(incident_data["logs"]))

        results = {
            "phase1_analysis": None,
            "phase2_hypothesis": None,
            "phase3_remediation": None,
            "execution_summary": {}
        }

        # Phase 1: Parallel diagnostic analysis
        self.logger.info("Phase 1: Running diagnostic agents in parallel")
        phase1_results = await self._execute_phase1_parallel(incident_data)
        results["phase1_analysis"] = phase1_results

        # Check if we have enough successful results to continue
        successful_results = [r for r in phase1_results.values()
                            if r and r.status == AgentStatus.COMPLETED]

        if len(successful_results) == 0:
            self.logger.error("All diagnostic agents failed")
            results["execution_summary"] = {
                "status": "failed",
                "error": "All diagnostic agents failed",
                "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000
            }
            return results

        self.logger.info(f"Phase 1 complete: {len(successful_results)}/{len(phase1_results)} agents succeeded")

        # Phase 2: Hypothesis generation
        self.logger.info("Phase 2: Generating hypotheses")
        phase2_result = await self._execute_phase2_hypothesis(phase1_results, incident_data)
        results["phase2_hypothesis"] = phase2_result

        if phase2_result and phase2_result.status == AgentStatus.COMPLETED and phase2_result.findings:
            self.logger.info(f"Generated {len(phase2_result.findings)} hypotheses")

            # Phase 3: Remediation planning
            self.logger.info("Phase 3: Creating remediation plan")
            phase3_result = await self._execute_phase3_remediation(phase2_result, incident_data)
            results["phase3_remediation"] = phase3_result

            if phase3_result and phase3_result.status == AgentStatus.COMPLETED:
                self.logger.info(f"Generated {len(phase3_result.findings)} remediation plans")
        else:
            self.logger.warning("Phase 2 failed or produced no hypotheses. Skipping remediation")

        # Execution summary
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        results["execution_summary"] = {
            "status": "completed",
            "total_agents": 6,
            "successful_agents": len(successful_results) + (1 if phase2_result and phase2_result.status == AgentStatus.COMPLETED else 0),
            "execution_time_ms": execution_time,
            "phases_completed": 3 if results["phase3_remediation"] else (2 if results["phase2_hypothesis"] else 1),
            "llm_enabled": self.use_llm,
            "pii_filtering": self.filter_pii
        }

        self.logger.info(f"Async RCA chain complete in {execution_time:.0f}ms")
        return results

    async def _execute_phase1_parallel(self, incident_data: Dict) -> Dict[str, BaseAgentOutput]:
        """Execute phase 1: parallel diagnostic analysis using asyncio.gather"""
        self.logger.info("Executing Phase 1 agents in parallel")

        # Create tasks for parallel execution
        tasks = [
            self._execute_agent_safe(
                self.log_analyzer,
                "log_analysis",
                {
                    "logs": incident_data.get("logs", []),
                    "time_range": incident_data.get("time_range", {}),
                    "incident_time": incident_data.get("incident_time")
                },
                incident_data.get("parameters", {})
            ),
            self._execute_agent_safe(
                self.metrics_analyzer,
                "metrics_analysis",
                {
                    "metrics": incident_data.get("metrics", []),
                    "time_range": incident_data.get("time_range", {}),
                    "incident_time": incident_data.get("incident_time")
                },
                incident_data.get("parameters", {})
            ),
            self._execute_agent_safe(
                self.change_correlator,
                "change_correlation",
                {
                    "changes": incident_data.get("changes", []),
                    "incident_time": incident_data.get("incident_time"),
                    "affected_services": incident_data.get("affected_services", [])
                },
                incident_data.get("parameters", {})
            ),
            self._execute_agent_safe(
                self.topology_inference,
                "topology",
                {
                    "logs": incident_data.get("logs", []),
                    "traces": incident_data.get("traces", []),
                    "metrics": incident_data.get("metrics", [])
                },
                incident_data.get("parameters", {})
            )
        ]

        # Execute all in parallel
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Map results back to keys
        keys = ["log_analysis", "metrics_analysis", "change_correlation", "topology"]
        results = {}

        for key, result in zip(keys, results_list):
            if isinstance(result, Exception):
                self.logger.error(f"{key} failed with exception", error=str(result))
                results[key] = self._create_error_result(key, str(result))
            else:
                results[key] = result

        return results

    async def _execute_agent_safe(self, agent, key: str, context_data: Dict, parameters: Dict) -> BaseAgentOutput:
        """Execute single agent with error handling"""
        try:
            input_data = BaseAgentInput(
                context=context_data,
                parameters=parameters
            )
            # Use execute_async if available, otherwise fallback to sync execute
            if hasattr(agent, 'execute_async'):
                result = await agent.execute_async(input_data)
            else:
                # For agents not yet upgraded, run sync version in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, agent.execute, input_data)

            self.logger.info(f"{key} completed successfully",
                           findings_count=len(result.findings),
                           execution_time_ms=result.execution_time_ms)
            return result

        except Exception as e:
            self.logger.error(f"{key} failed", error=str(e))
            if self.error_strategy == "fail_fast":
                raise
            return self._create_error_result(agent.name, str(e))

    async def _execute_phase2_hypothesis(self, phase1_results: Dict, incident_data: Dict) -> Optional[BaseAgentOutput]:
        """Execute phase 2: hypothesis generation"""
        try:
            # Collect findings from successful agents
            context = {
                "incident_description": incident_data.get("description", ""),
                "incident_time": incident_data.get("incident_time"),
                "affected_services": incident_data.get("affected_services", [])
            }

            # Add findings from each agent
            for key in ["log_analysis", "metrics_analysis", "change_correlation", "topology"]:
                result = phase1_results.get(key)
                if result and result.status == AgentStatus.COMPLETED:
                    context[f"{key.split('_')[0]}_findings"] = result.findings

            input_data = BaseAgentInput(
                context=context,
                parameters=incident_data.get("parameters", {})
            )

            if hasattr(self.hypothesis_generator, 'execute_async'):
                return await self.hypothesis_generator.execute_async(input_data)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.hypothesis_generator.execute, input_data)

        except Exception as e:
            self.logger.error("HypothesisGenerator failed", error=str(e))
            return self._create_error_result("HypothesisGeneratorAgent", str(e))

    async def _execute_phase3_remediation(self, hypothesis_result: BaseAgentOutput,
                                         incident_data: Dict) -> Optional[BaseAgentOutput]:
        """Execute phase 3: remediation planning"""
        try:
            if not hypothesis_result.findings:
                return None

            # Use top hypothesis
            top_hypothesis = hypothesis_result.findings[0]

            context = {
                "incident_description": incident_data.get("description", ""),
                "validated_hypothesis": {
                    "description": top_hypothesis.description,
                    "evidence": top_hypothesis.evidence,
                    "failure_pattern": top_hypothesis.metadata.get("failure_pattern", ""),
                    "affected_components": top_hypothesis.metadata.get("affected_components", [])
                },
                "current_state": incident_data.get("current_state", {}),
                "capabilities": incident_data.get("capabilities", {
                    "can_rollback": True,
                    "can_scale": True,
                    "can_restart": True
                })
            }

            input_data = BaseAgentInput(
                context=context,
                parameters=incident_data.get("parameters", {})
            )

            if hasattr(self.remediation_planner, 'execute_async'):
                return await self.remediation_planner.execute_async(input_data)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.remediation_planner.execute, input_data)

        except Exception as e:
            self.logger.error("RemediationPlanner failed", error=str(e))
            return self._create_error_result("RemediationPlannerAgent", str(e))

    def _create_error_result(self, agent_name: str, error_message: str) -> BaseAgentOutput:
        """Create error result for failed agent"""
        return BaseAgentOutput(
            agent_name=agent_name,
            status=AgentStatus.FAILED,
            findings=[],
            summary=f"Agent execution failed: {error_message}",
            confidence=ConfidenceLevel.UNCERTAIN,
            next_steps=["Review agent configuration", "Check input data"],
            errors=[error_message],
            execution_time_ms=0
        )

    def print_results(self, results: Dict[str, Any]):
        """Pretty print orchestration results"""
        print("\n" + "=" * 80)
        print("ASYNC RCA CHAIN EXECUTION RESULTS")
        print("=" * 80)

        # Phase 1
        print("\n[Phase 1: Diagnostic Analysis]")
        if results.get("phase1_analysis"):
            for agent_type, result in results["phase1_analysis"].items():
                status_icon = "✓" if result.status == AgentStatus.COMPLETED else "✗"
                print(f"  {status_icon} {agent_type}: {result.summary}")
                if result.findings:
                    print(f"    Findings: {len(result.findings)}")

        # Phase 2
        print("\n[Phase 2: Hypothesis Generation]")
        if results.get("phase2_hypothesis"):
            result = results["phase2_hypothesis"]
            status_icon = "✓" if result.status == AgentStatus.COMPLETED else "✗"
            print(f"  {status_icon} {result.summary}")
            for i, finding in enumerate(result.findings[:3], 1):
                print(f"    {i}. {finding.description}")
                print(f"       Score: {finding.metadata.get('hypothesis_score', 'N/A')}/100")

        # Phase 3
        print("\n[Phase 3: Remediation Planning]")
        if results.get("phase3_remediation"):
            result = results["phase3_remediation"]
            status_icon = "✓" if result.status == AgentStatus.COMPLETED else "✗"
            print(f"  {status_icon} {result.summary}")
            for i, plan in enumerate(result.findings, 1):
                print(f"    Plan {i}: {plan.description}")
                print(f"    Type: {plan.metadata.get('plan_type', 'N/A')}")
                print(f"    Est. Time: {plan.metadata.get('estimated_time_minutes', 'N/A')} minutes")

        # Summary
        print("\n[Execution Summary]")
        summary = results.get("execution_summary", {})
        print(f"  Status: {summary.get('status', 'unknown')}")
        print(f"  Total Time: {summary.get('execution_time_ms', 0):.0f}ms")
        print(f"  Agents: {summary.get('successful_agents', 0)}/{summary.get('total_agents', 0)} successful")
        print(f"  LLM Enabled: {summary.get('llm_enabled', False)}")
        print(f"  PII Filtering: {summary.get('pii_filtering', False)}")
        print("=" * 80 + "\n")
