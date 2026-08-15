"""
Streaming Orchestrator Wrapper
Extends AsyncAgentOrchestrator with real-time WebSocket streaming
"""

from typing import Dict, Any, Optional
import asyncio
from chains.async_orchestrator import AsyncAgentOrchestrator
from schemas import BaseAgentInput


def _extract_findings(result) -> list:
    """
    Safely extract findings from a phase result.

    Phase results are BaseAgentOutput models (attribute access), but may be an
    Exception when asyncio.gather ran with return_exceptions=True, or None when
    an agent was skipped.
    """
    if result is None or isinstance(result, Exception):
        return []
    findings = getattr(result, "findings", None)
    if findings is None and isinstance(result, dict):
        findings = result.get("findings")
    return findings or []


class StreamingOrchestrator(AsyncAgentOrchestrator):
    """
    Orchestrator with real-time streaming capabilities

    Sends live updates via WebSocket during agent execution:
    - Agent start/complete notifications
    - Progress updates
    - Findings as discovered
    - Phase transitions
    """

    def __init__(
        self,
        websocket_manager=None,
        analysis_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.ws_manager = websocket_manager
        self.analysis_id = analysis_id

    async def _execute_agent_with_streaming(
        self,
        agent_name: str,
        agent_instance,
        input_data: BaseAgentInput
    ):
        """Execute agent with real-time status streaming"""

        # Send agent start notification
        if self.ws_manager and self.analysis_id:
            await self.ws_manager.send_agent_status(
                self.analysis_id,
                agent_name,
                "running",
                0.0,
                f"Starting {agent_name}..."
            )

        try:
            # Execute agent
            result = await agent_instance.execute_async(input_data)

            # Send findings as they come
            if self.ws_manager and self.analysis_id and result.findings:
                for finding in result.findings:
                    await self.ws_manager.send_finding(
                        self.analysis_id,
                        agent_name,
                        finding.dict() if hasattr(finding, 'dict') else finding
                    )

            # Send completion
            if self.ws_manager and self.analysis_id:
                await self.ws_manager.send_agent_status(
                    self.analysis_id,
                    agent_name,
                    "completed",
                    100.0,
                    f"{agent_name} completed with {len(result.findings)} findings"
                )

            return result

        except Exception as e:
            # Send error
            if self.ws_manager and self.analysis_id:
                await self.ws_manager.send_error(
                    self.analysis_id,
                    agent_name,
                    str(e)
                )
            raise

    async def _execute_phase1_parallel(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Phase 1 with streaming"""

        if self.ws_manager and self.analysis_id:
            await self.ws_manager.send_phase_status(
                self.analysis_id,
                "phase1",
                "running",
                0,
                4
            )

        # Import agents
        from agents import (
            LogAnalyzerAgent,
            MetricsAnalyzerAgent,
            ChangeCorrelatorAgent,
            TopologyInferenceAgent
        )

        # Initialize agents
        log_agent = LogAnalyzerAgent(use_llm=self.use_llm)
        metrics_agent = MetricsAnalyzerAgent(use_llm=self.use_llm)
        change_agent = ChangeCorrelatorAgent(use_llm=self.use_llm)
        topology_agent = TopologyInferenceAgent(use_llm=self.use_llm)

        # Create input
        agent_input = BaseAgentInput(context=incident_data)

        # Execute in parallel with streaming
        log_task = self._execute_agent_with_streaming("LogAnalyzer", log_agent, agent_input)
        metrics_task = self._execute_agent_with_streaming("MetricsAnalyzer", metrics_agent, agent_input)
        change_task = self._execute_agent_with_streaming("ChangeCorrelator", change_agent, agent_input)
        topology_task = self._execute_agent_with_streaming("TopologyInference", topology_agent, agent_input)

        # Gather results
        log_result, metrics_result, change_result, topology_result = await asyncio.gather(
            log_task, metrics_task, change_task, topology_task,
            return_exceptions=True
        )

        if self.ws_manager and self.analysis_id:
            await self.ws_manager.send_phase_status(
                self.analysis_id,
                "phase1",
                "completed",
                4,
                4
            )

        return {
            "log_analyzer": log_result,
            "metrics_analyzer": metrics_result,
            "change_correlator": change_result,
            "topology_inference": topology_result
        }

    async def execute_rca_chain(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute RCA chain with real-time streaming"""

        import time
        start_time = time.time()

        try:
            # Phase 1
            phase1_results = await self._execute_phase1_parallel(incident_data)

            # Phase 2
            if self.ws_manager and self.analysis_id:
                await self.ws_manager.send_phase_status(
                    self.analysis_id,
                    "phase2",
                    "running",
                    0,
                    1
                )

            from agents import HypothesisGeneratorAgent

            hypothesis_agent = HypothesisGeneratorAgent(use_llm=self.use_llm)

            # Prepare context with phase 1 findings
            hypothesis_context = {
                **incident_data,
                "log_findings": _extract_findings(phase1_results.get("log_analyzer")),
                "metrics_findings": _extract_findings(phase1_results.get("metrics_analyzer")),
                "change_findings": _extract_findings(phase1_results.get("change_correlator")),
                "topology_findings": _extract_findings(phase1_results.get("topology_inference"))
            }

            hypothesis_input = BaseAgentInput(context=hypothesis_context)
            hypothesis_result = await self._execute_agent_with_streaming(
                "HypothesisGenerator",
                hypothesis_agent,
                hypothesis_input
            )

            if self.ws_manager and self.analysis_id:
                await self.ws_manager.send_phase_status(
                    self.analysis_id,
                    "phase2",
                    "completed",
                    1,
                    1
                )

            # Phase 3
            if self.ws_manager and self.analysis_id:
                await self.ws_manager.send_phase_status(
                    self.analysis_id,
                    "phase3",
                    "running",
                    0,
                    1
                )

            from agents import RemediationPlannerAgent

            remediation_agent = RemediationPlannerAgent(use_llm=self.use_llm)

            remediation_context = {
                **incident_data,
                "validated_hypothesis": hypothesis_result.dict() if hasattr(hypothesis_result, 'dict') else hypothesis_result
            }

            remediation_input = BaseAgentInput(context=remediation_context)
            remediation_result = await self._execute_agent_with_streaming(
                "RemediationPlanner",
                remediation_agent,
                remediation_input
            )

            if self.ws_manager and self.analysis_id:
                await self.ws_manager.send_phase_status(
                    self.analysis_id,
                    "phase3",
                    "completed",
                    1,
                    1
                )

            # Complete
            execution_time = (time.time() - start_time) * 1000

            results = {
                "phase1": phase1_results,
                "phase2": {"hypothesis_generator": hypothesis_result},
                "phase3": {"remediation_planner": remediation_result},
                "success": True,
                "execution_time_ms": execution_time
            }

            if self.ws_manager and self.analysis_id:
                await self.ws_manager.send_analysis_complete(
                    self.analysis_id,
                    True,
                    f"RCA completed with {len(hypothesis_result.findings if hasattr(hypothesis_result, 'findings') else [])} hypotheses",
                    execution_time
                )

            return results

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000

            if self.ws_manager and self.analysis_id:
                await self.ws_manager.send_analysis_complete(
                    self.analysis_id,
                    False,
                    f"RCA failed: {str(e)}",
                    execution_time
                )

            raise
