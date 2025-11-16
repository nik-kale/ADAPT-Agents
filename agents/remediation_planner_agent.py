"""
Remediation Planner Agent
Generates actionable remediation plans based on validated hypotheses.
"""

from typing import Dict, Any, List
from datetime import datetime
from schemas import (
    BaseAgent, BaseAgentInput, BaseAgentOutput,
    Finding, AgentStatus, ConfidenceLevel, AgentCapabilities
)


class RemediationPlannerAgent(BaseAgent):
    """
    Specialized agent for generating remediation plans:
    - Immediate mitigation steps
    - Root cause fix procedures
    - Validation and rollback plans
    - Prevention measures
    """

    def __init__(self):
        capabilities = AgentCapabilities(
            name="RemediationPlannerAgent",
            description="Generates actionable remediation plans for validated root causes",
            input_types=["hypothesis", "root_cause"],
            output_types=["remediation_plan", "action_steps"],
            dependencies=["HypothesisGeneratorAgent"],
            supports_streaming=False
        )
        super().__init__("RemediationPlannerAgent", capabilities)

    def execute(self, input_data: BaseAgentInput) -> BaseAgentOutput:
        """Execute remediation planning"""
        start_time = datetime.now()

        try:
            context = input_data.context
            parameters = input_data.parameters or {}

            validated_hypothesis = context.get("validated_hypothesis", {})
            current_state = context.get("current_state", {})
            capabilities = context.get("capabilities", {})

            # Generate remediation plans
            plans = self._generate_plans(validated_hypothesis, current_state, capabilities, parameters)

            summary = self._generate_summary(plans)
            confidence = self._calculate_confidence(plans)
            next_steps = self._generate_next_steps(plans)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return BaseAgentOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                findings=plans,
                summary=summary,
                confidence=confidence,
                next_steps=next_steps,
                errors=[],
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return BaseAgentOutput(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                findings=[],
                summary=f"Planning failed: {str(e)}",
                confidence=ConfidenceLevel.UNCERTAIN,
                next_steps=["Review hypothesis data", "Ensure root cause is validated"],
                errors=[str(e)],
                execution_time_ms=execution_time
            )

    def _generate_plans(self, hypothesis: Dict, current_state: Dict,
                       capabilities: Dict, parameters: Dict) -> List[Finding]:
        """Generate remediation plans"""
        plans = []

        failure_pattern = hypothesis.get("failure_pattern", "")
        description = hypothesis.get("description", "")

        # Generate immediate mitigation plan
        immediate_plan = self._generate_immediate_plan(failure_pattern, description, current_state, capabilities)
        if immediate_plan:
            plans.append(immediate_plan)

        # Generate root cause fix plan
        fix_plan = self._generate_fix_plan(failure_pattern, description, capabilities)
        if fix_plan:
            plans.append(fix_plan)

        # Generate prevention plan
        prevention_plan = self._generate_prevention_plan(failure_pattern, description)
        if prevention_plan:
            plans.append(prevention_plan)

        return plans

    def _generate_immediate_plan(self, pattern: str, description: str,
                                current_state: Dict, capabilities: Dict) -> Finding:
        """Generate immediate mitigation plan"""

        # Pattern-based plan generation
        if "deployment" in pattern or "deployment" in description.lower():
            return self._create_rollback_plan(description, capabilities)
        elif "pool" in pattern or "pool" in description.lower():
            return self._create_config_revert_plan(description, capabilities)
        elif "memory" in description.lower() or "cpu" in description.lower():
            return self._create_scale_plan(description, capabilities)
        elif "timeout" in pattern or "cascade" in pattern:
            return self._create_circuit_breaker_plan(description)
        else:
            return self._create_generic_mitigation_plan(description, capabilities)

    def _create_rollback_plan(self, description: str, capabilities: Dict) -> Finding:
        """Create rollback remediation plan"""
        can_rollback = capabilities.get("can_rollback", True)

        steps = [
            {
                "step_number": 1,
                "action": "Identify target rollback version (previous stable)",
                "command": "kubectl rollout history deployment/<service-name>",
                "expected_outcome": "Previous version identified",
                "validation": "Review deployment history",
                "rollback": "N/A",
                "estimated_duration_minutes": 1,
                "risk": "low"
            },
            {
                "step_number": 2,
                "action": "Execute rollback",
                "command": "kubectl rollout undo deployment/<service-name>" if can_rollback else "Manual rollback required",
                "expected_outcome": "Service rolls back to previous version",
                "validation": "kubectl rollout status deployment/<service-name>",
                "rollback": "Re-deploy current version if needed",
                "estimated_duration_minutes": 3,
                "risk": "low" if can_rollback else "medium"
            },
            {
                "step_number": 3,
                "action": "Monitor service health and error rates",
                "command": "Check monitoring dashboard for error rates and health checks",
                "expected_outcome": "Error rate decreases, health checks pass",
                "validation": "Error rate < 0.1% for 5 minutes",
                "rollback": "If errors persist, investigate other causes",
                "estimated_duration_minutes": 5,
                "risk": "low"
            },
            {
                "step_number": 4,
                "action": "Verify customer impact resolved",
                "command": "Check customer-facing metrics and support tickets",
                "expected_outcome": "Customer impact eliminated",
                "validation": "No new incident reports",
                "rollback": "N/A",
                "estimated_duration_minutes": 3,
                "risk": "low"
            }
        ]

        return Finding(
            type="remediation_plan",
            description="Rollback deployment to previous stable version",
            confidence=ConfidenceLevel.HIGH if can_rollback else ConfidenceLevel.MEDIUM,
            evidence=[
                "Rollback is safest immediate mitigation for deployment issues",
                "Previous version was stable",
                "Rollback procedure is well-tested"
            ],
            severity="CRITICAL",
            metadata={
                "plan_type": "immediate",
                "estimated_time_minutes": 12,
                "risk_level": "low" if can_rollback else "medium",
                "requires_approval": not can_rollback,
                "affected_components": ["service"],
                "steps": steps,
                "success_criteria": [
                    "Service running previous version",
                    "Error rate < 0.1%",
                    "Health checks passing",
                    "Customer impact resolved"
                ],
                "rollback_plan": [
                    "If rollback fails: manually restart pods",
                    "If still failing: scale to 0 and back up",
                    "Escalation: page on-call architect"
                ]
            }
        )

    def _create_config_revert_plan(self, description: str, capabilities: Dict) -> Finding:
        """Create configuration revert plan"""
        steps = [
            {
                "step_number": 1,
                "action": "Identify configuration change to revert",
                "command": "kubectl get configmap <service>-config -o yaml",
                "expected_outcome": "Configuration change identified",
                "validation": "Review recent config changes",
                "rollback": "N/A",
                "estimated_duration_minutes": 2,
                "risk": "low"
            },
            {
                "step_number": 2,
                "action": "Revert configuration to previous value",
                "command": "kubectl edit configmap <service>-config",
                "expected_outcome": "Configuration updated",
                "validation": "kubectl get configmap <service>-config -o yaml",
                "rollback": "Re-apply current config if needed",
                "estimated_duration_minutes": 2,
                "risk": "low"
            },
            {
                "step_number": 3,
                "action": "Restart service to apply configuration",
                "command": "kubectl rollout restart deployment/<service>",
                "expected_outcome": "Pods restart with new configuration",
                "validation": "kubectl rollout status deployment/<service>",
                "rollback": "Revert config and restart again",
                "estimated_duration_minutes": 3,
                "risk": "medium"
            },
            {
                "step_number": 4,
                "action": "Verify issue resolved",
                "command": "Check logs and metrics for errors",
                "expected_outcome": "Errors stopped",
                "validation": "No errors for 5 minutes",
                "rollback": "Investigate if errors persist",
                "estimated_duration_minutes": 5,
                "risk": "low"
            }
        ]

        return Finding(
            type="remediation_plan",
            description="Revert configuration change to previous stable value",
            confidence=ConfidenceLevel.HIGH,
            evidence=[
                "Configuration change correlates with issue",
                "Previous configuration was stable",
                "Change is easily reversible"
            ],
            severity="CRITICAL",
            metadata={
                "plan_type": "immediate",
                "estimated_time_minutes": 12,
                "risk_level": "low",
                "requires_approval": False,
                "steps": steps,
                "success_criteria": [
                    "Configuration reverted",
                    "Service restarted successfully",
                    "Errors eliminated",
                    "Performance restored"
                ]
            }
        )

    def _create_scale_plan(self, description: str, capabilities: Dict) -> Finding:
        """Create resource scaling plan"""
        can_scale = capabilities.get("can_scale", True)

        steps = [
            {
                "step_number": 1,
                "action": "Identify resource bottleneck",
                "command": "Review CPU/Memory metrics",
                "expected_outcome": "Bottleneck resource identified",
                "validation": "Metrics show >80% utilization",
                "rollback": "N/A",
                "estimated_duration_minutes": 2,
                "risk": "low"
            },
            {
                "step_number": 2,
                "action": "Scale up service (horizontal)",
                "command": "kubectl scale deployment/<service> --replicas=<new-count>" if can_scale else "Manual scaling required",
                "expected_outcome": "Additional replicas deployed",
                "validation": "kubectl get pods | grep <service>",
                "rollback": "Scale back down if issues occur",
                "estimated_duration_minutes": 3,
                "risk": "low" if can_scale else "medium"
            },
            {
                "step_number": 3,
                "action": "Monitor resource utilization",
                "command": "Check resource metrics dashboard",
                "expected_outcome": "Resource utilization decreases below 70%",
                "validation": "CPU/Memory < 70% for 5 minutes",
                "rollback": "Continue scaling if still high",
                "estimated_duration_minutes": 5,
                "risk": "low"
            }
        ]

        return Finding(
            type="remediation_plan",
            description="Scale up resources to handle load",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=[
                "Resource exhaustion detected",
                "Scaling is quick mitigation",
                "Root cause fix can follow"
            ],
            severity="HIGH",
            metadata={
                "plan_type": "immediate",
                "estimated_time_minutes": 10,
                "risk_level": "low",
                "requires_approval": False,
                "steps": steps,
                "success_criteria": [
                    "More replicas running",
                    "Resource utilization < 70%",
                    "Performance improved"
                ]
            }
        )

    def _create_circuit_breaker_plan(self, description: str) -> Finding:
        """Create circuit breaker plan for cascading failures"""
        return Finding(
            type="remediation_plan",
            description="Enable circuit breaker to stop cascading failures",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=[
                "Cascading failure pattern detected",
                "Circuit breaker prevents propagation",
                "Allows time to fix root cause"
            ],
            severity="HIGH",
            metadata={
                "plan_type": "immediate",
                "estimated_time_minutes": 5,
                "risk_level": "medium",
                "requires_approval": True,
                "steps": [
                    {
                        "step_number": 1,
                        "action": "Enable circuit breaker for failing dependency",
                        "command": "Update service mesh configuration",
                        "expected_outcome": "Calls to failing service stopped",
                        "validation": "Monitor request metrics",
                        "estimated_duration_minutes": 5,
                        "risk": "medium"
                    }
                ],
                "success_criteria": ["Circuit breaker active", "Cascading failures stopped"]
            }
        )

    def _create_generic_mitigation_plan(self, description: str, capabilities: Dict) -> Finding:
        """Create generic mitigation plan"""
        can_restart = capabilities.get("can_restart", True)

        return Finding(
            type="remediation_plan",
            description="Restart affected services as immediate mitigation",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Restart may clear transient state", "Low-risk immediate action"],
            severity="MEDIUM",
            metadata={
                "plan_type": "immediate",
                "estimated_time_minutes": 5,
                "risk_level": "low",
                "requires_approval": False,
                "steps": [
                    {
                        "step_number": 1,
                        "action": "Restart affected services",
                        "command": "kubectl rollout restart deployment/<service>" if can_restart else "Manual restart required",
                        "expected_outcome": "Services restart",
                        "validation": "Pods running",
                        "estimated_duration_minutes": 5,
                        "risk": "low"
                    }
                ],
                "success_criteria": ["Services restarted", "Health checks passing"]
            }
        )

    def _generate_fix_plan(self, pattern: str, description: str, capabilities: Dict) -> Finding:
        """Generate root cause fix plan (longer-term)"""
        return Finding(
            type="remediation_plan",
            description="Root cause fix: investigate and patch underlying issue",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Addresses root cause", "Prevents recurrence"],
            severity="MEDIUM",
            metadata={
                "plan_type": "short_term",
                "estimated_time_minutes": 120,
                "risk_level": "medium",
                "requires_approval": True,
                "steps": [
                    {
                        "step_number": 1,
                        "action": "Deep-dive investigation of root cause",
                        "command": "Review code, logs, and metrics in detail",
                        "expected_outcome": "Root cause fully understood",
                        "validation": "Clear explanation of failure mechanism",
                        "estimated_duration_minutes": 60,
                        "risk": "low"
                    },
                    {
                        "step_number": 2,
                        "action": "Develop and test fix",
                        "command": "Code changes + unit/integration tests",
                        "expected_outcome": "Fix developed and tested",
                        "validation": "Tests pass, fix validated in staging",
                        "estimated_duration_minutes": 90,
                        "risk": "medium"
                    },
                    {
                        "step_number": 3,
                        "action": "Deploy fix to production",
                        "command": "Standard deployment process",
                        "expected_outcome": "Fix deployed successfully",
                        "validation": "No regression, issue resolved",
                        "estimated_duration_minutes": 30,
                        "risk": "medium"
                    }
                ],
                "success_criteria": ["Root cause eliminated", "Issue does not recur"]
            }
        )

    def _generate_prevention_plan(self, pattern: str, description: str) -> Finding:
        """Generate prevention/improvement plan"""
        return Finding(
            type="remediation_plan",
            description="Prevention: implement safeguards to prevent recurrence",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Long-term improvements", "Reduce future risk"],
            severity="LOW",
            metadata={
                "plan_type": "long_term",
                "estimated_time_minutes": 480,
                "risk_level": "low",
                "requires_approval": True,
                "steps": [
                    {
                        "step_number": 1,
                        "action": "Add monitoring and alerts for early detection",
                        "command": "Create alerts for key metrics/patterns",
                        "expected_outcome": "Proactive detection in future",
                        "validation": "Alerts tested and operational",
                        "estimated_duration_minutes": 120,
                        "risk": "low"
                    },
                    {
                        "step_number": 2,
                        "action": "Implement automated tests to catch issue",
                        "command": "Add test cases that would have caught this",
                        "expected_outcome": "Regression prevented",
                        "validation": "Tests added to CI/CD",
                        "estimated_duration_minutes": 180,
                        "risk": "low"
                    },
                    {
                        "step_number": 3,
                        "action": "Document incident and learnings",
                        "command": "Post-mortem document",
                        "expected_outcome": "Knowledge shared",
                        "validation": "Post-mortem reviewed",
                        "estimated_duration_minutes": 60,
                        "risk": "low"
                    }
                ],
                "success_criteria": [
                    "Monitoring in place",
                    "Tests prevent regression",
                    "Documentation complete"
                ]
            }
        )

    def _generate_summary(self, plans: List[Finding]) -> str:
        """Generate summary"""
        if not plans:
            return "No remediation plans generated"

        immediate = sum(1 for p in plans if p.metadata.get("plan_type") == "immediate")
        return f"Generated {len(plans)} remediation plans: {immediate} immediate, " \
               f"{len(plans) - immediate} longer-term. Execute in priority order."

    def _calculate_confidence(self, plans: List[Finding]) -> ConfidenceLevel:
        """Calculate confidence"""
        if not plans:
            return ConfidenceLevel.LOW

        # Confidence based on immediate plan availability
        immediate_plans = [p for p in plans if p.metadata.get("plan_type") == "immediate"]
        if immediate_plans and immediate_plans[0].confidence == ConfidenceLevel.HIGH:
            return ConfidenceLevel.HIGH
        return ConfidenceLevel.MEDIUM

    def _generate_next_steps(self, plans: List[Finding]) -> List[str]:
        """Generate next steps"""
        if not plans:
            return ["Unable to generate plans - review hypothesis"]

        # Extract first 3 steps from immediate plan
        immediate = [p for p in plans if p.metadata.get("plan_type") == "immediate"]
        if immediate:
            steps = immediate[0].metadata.get("steps", [])
            return [f"Step {s['step_number']}: {s['action']}" for s in steps[:3]]

        return ["Review and execute remediation plans in order"]
