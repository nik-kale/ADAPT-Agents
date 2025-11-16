"""
Hypothesis Generator Agent
Synthesizes findings from multiple agents to generate root cause hypotheses.
"""

from typing import Dict, Any, List
from datetime import datetime
from schemas import (
    BaseAgent, BaseAgentInput, BaseAgentOutput,
    Finding, AgentStatus, ConfidenceLevel, AgentCapabilities
)


class HypothesisGeneratorAgent(BaseAgent):
    """
    Specialized agent for generating root cause hypotheses:
    - Synthesizes findings from multiple diagnostic agents
    - Generates ranked hypotheses
    - Suggests validation tests
    - Identifies evidence gaps
    """

    def __init__(self):
        capabilities = AgentCapabilities(
            name="HypothesisGeneratorAgent",
            description="Generates and ranks root cause hypotheses from multi-source evidence",
            input_types=["findings", "multi_agent_output"],
            output_types=["hypotheses", "ranked_findings"],
            dependencies=["LogAnalyzerAgent", "MetricsAnalyzerAgent", "ChangeCorrelatorAgent"],
            supports_streaming=False
        )
        super().__init__("HypothesisGeneratorAgent", capabilities)

    # Known failure patterns
    FAILURE_PATTERNS = {
        "deployment_induced_memory_leak": {
            "indicators": ["deployment", "memory", "oom"],
            "score_bonus": 20
        },
        "resource_pool_exhaustion": {
            "indicators": ["config_change", "connection", "pool", "exhausted"],
            "score_bonus": 20
        },
        "cascading_timeout": {
            "indicators": ["timeout", "cascade", "latency"],
            "score_bonus": 15
        },
        "database_performance": {
            "indicators": ["database", "query", "slow", "timeout"],
            "score_bonus": 15
        }
    }

    def execute(self, input_data: BaseAgentInput) -> BaseAgentOutput:
        """Execute hypothesis generation"""
        start_time = datetime.now()

        try:
            context = input_data.context
            parameters = input_data.parameters or {}

            # Collect findings from all agents
            all_findings = self._collect_findings(context)

            # Generate hypotheses
            hypotheses = self._generate_hypotheses(all_findings, context, parameters)

            # Rank hypotheses
            hypotheses = self._rank_hypotheses(hypotheses)

            # Limit to top N
            max_hypotheses = parameters.get("max_hypotheses", 5)
            hypotheses = hypotheses[:max_hypotheses]

            summary = self._generate_summary(hypotheses)
            confidence = self._calculate_confidence(hypotheses)
            next_steps = self._generate_next_steps(hypotheses)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return BaseAgentOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                findings=hypotheses,
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
                summary=f"Hypothesis generation failed: {str(e)}",
                confidence=ConfidenceLevel.UNCERTAIN,
                next_steps=["Review input findings", "Ensure diagnostic agents ran successfully"],
                errors=[str(e)],
                execution_time_ms=execution_time
            )

    def _collect_findings(self, context: Dict) -> List[Finding]:
        """Collect findings from all agent outputs"""
        all_findings = []

        # Collect from each agent type
        for key in ["log_findings", "metrics_findings", "change_findings", "topology_findings"]:
            findings_data = context.get(key, [])
            # If findings are already Finding objects, use them
            # Otherwise, convert from dict
            for f in findings_data:
                if isinstance(f, Finding):
                    all_findings.append(f)
                elif isinstance(f, dict):
                    # Convert dict to Finding
                    all_findings.append(Finding(**f))

        return all_findings

    def _generate_hypotheses(self, findings: List[Finding], context: Dict, parameters: Dict) -> List[Finding]:
        """Generate hypotheses from findings"""
        hypotheses = []

        # Group findings by type/service for pattern detection
        deployment_findings = [f for f in findings if "deploy" in f.description.lower() or f.type == "correlated_change"]
        memory_findings = [f for f in findings if "memory" in f.description.lower() or "oom" in f.description.lower()]
        db_findings = [f for f in findings if "database" in f.description.lower() or "connection" in f.description.lower()]
        latency_findings = [f for f in findings if "latency" in f.description.lower() or "timeout" in f.description.lower()]
        config_findings = [f for f in findings if "config" in f.description.lower()]

        # Pattern 1: Deployment-induced memory leak
        if deployment_findings and memory_findings:
            hypothesis = self._create_deployment_memory_hypothesis(deployment_findings, memory_findings, findings)
            if hypothesis:
                hypotheses.append(hypothesis)

        # Pattern 2: Config-induced resource exhaustion
        if config_findings and db_findings:
            hypothesis = self._create_config_pool_hypothesis(config_findings, db_findings, findings)
            if hypothesis:
                hypotheses.append(hypothesis)

        # Pattern 3: Cascading timeout
        if latency_findings and len(latency_findings) >= 2:
            hypothesis = self._create_cascading_timeout_hypothesis(latency_findings, findings)
            if hypothesis:
                hypotheses.append(hypothesis)

        # Pattern 4: General deployment issue
        if deployment_findings and not memory_findings:
            # Deployment with other errors
            error_findings = [f for f in findings if f.severity in ["CRITICAL", "HIGH"] and f != deployment_findings[0]]
            if error_findings:
                hypothesis = self._create_deployment_error_hypothesis(deployment_findings, error_findings)
                if hypothesis:
                    hypotheses.append(hypothesis)

        return hypotheses

    def _create_deployment_memory_hypothesis(self, deploy_findings: List[Finding],
                                            memory_findings: List[Finding],
                                            all_findings: List[Finding]) -> Finding:
        """Create hypothesis for deployment-induced memory leak"""
        deploy = deploy_findings[0]
        memory = memory_findings[0]

        evidence = [
            f"[Change] {deploy.description}",
            f"[Metrics] {memory.description}",
        ]

        # Add supporting evidence from logs
        log_evidence = [f for f in all_findings if f.type in ["error_pattern", "anomaly"] and
                       ("error" in f.description.lower() or "exception" in f.description.lower())]
        for log_f in log_evidence[:2]:
            evidence.append(f"[Logs] {log_f.description}")

        # Calculate hypothesis score
        score = self._calculate_hypothesis_score(evidence, ["changes", "metrics", "logs"],
                                                [deploy, memory] + log_evidence[:2],
                                                "deployment_induced_memory_leak")

        return Finding(
            type="hypothesis",
            description="Recent deployment introduced memory leak causing resource exhaustion and failures",
            confidence=ConfidenceLevel.HIGH if score >= 70 else ConfidenceLevel.MEDIUM,
            evidence=evidence,
            severity="CRITICAL",
            metadata={
                "hypothesis_score": score,
                "evidence_sources": ["changes", "metrics", "logs"],
                "failure_pattern": "deployment_induced_memory_leak",
                "validation_tests": [
                    "Review recent deployment code changes for object retention issues",
                    "Analyze heap dump for memory leak patterns",
                    "Compare memory profile before/after deployment",
                    "Test rollback to previous version"
                ]
            }
        )

    def _create_config_pool_hypothesis(self, config_findings: List[Finding],
                                      db_findings: List[Finding],
                                      all_findings: List[Finding]) -> Finding:
        """Create hypothesis for configuration-induced pool exhaustion"""
        config = config_findings[0]
        db = db_findings[0]

        evidence = [
            f"[Change] {config.description}",
            f"[Logs] {db.description}",
        ]

        # Add metrics if available
        metrics_evidence = [f for f in all_findings if f.type in ["anomaly", "threshold_violation"]]
        for m in metrics_evidence[:1]:
            evidence.append(f"[Metrics] {m.description}")

        score = self._calculate_hypothesis_score(evidence, ["changes", "logs", "metrics"],
                                                [config, db] + metrics_evidence[:1],
                                                "resource_pool_exhaustion")

        return Finding(
            type="hypothesis",
            description="Configuration change reduced resource pool size below required capacity",
            confidence=ConfidenceLevel.HIGH if score >= 70 else ConfidenceLevel.MEDIUM,
            evidence=evidence,
            severity="CRITICAL",
            metadata={
                "hypothesis_score": score,
                "evidence_sources": ["changes", "logs", "metrics"],
                "failure_pattern": "resource_pool_exhaustion",
                "validation_tests": [
                    "Review configuration change and capacity requirements",
                    "Check current vs. previous pool size settings",
                    "Test restoring previous configuration",
                    "Monitor resource pool utilization metrics"
                ]
            }
        )

    def _create_cascading_timeout_hypothesis(self, latency_findings: List[Finding],
                                            all_findings: List[Finding]) -> Finding:
        """Create hypothesis for cascading timeout failure"""
        evidence = []
        for f in latency_findings[:3]:
            evidence.append(f"[Logs/Metrics] {f.description}")

        # Check for topology info
        topo_findings = [f for f in all_findings if f.type in ["dependency", "bottleneck"]]
        for t in topo_findings[:1]:
            evidence.append(f"[Topology] {t.description}")

        sources = ["logs", "metrics"]
        if topo_findings:
            sources.append("topology")

        score = self._calculate_hypothesis_score(evidence, sources, latency_findings[:3] + topo_findings[:1],
                                                "cascading_timeout")

        return Finding(
            type="hypothesis",
            description="Downstream service degradation cascaded upstream causing widespread timeouts",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=evidence,
            severity="HIGH",
            metadata={
                "hypothesis_score": score,
                "evidence_sources": sources,
                "failure_pattern": "cascading_timeout",
                "validation_tests": [
                    "Identify root service with initial slowdown",
                    "Review database slow query logs",
                    "Check for resource contention or locks",
                    "Analyze service dependency chain"
                ]
            }
        )

    def _create_deployment_error_hypothesis(self, deploy_findings: List[Finding],
                                           error_findings: List[Finding]) -> Finding:
        """Create general deployment-related hypothesis"""
        deploy = deploy_findings[0]

        evidence = [f"[Change] {deploy.description}"]
        for err in error_findings[:2]:
            evidence.append(f"[{err.type.title()}] {err.description}")

        score = self._calculate_hypothesis_score(evidence, ["changes", "logs"],
                                                [deploy] + error_findings[:2],
                                                "deployment_issue")

        return Finding(
            type="hypothesis",
            description="Recent deployment introduced errors or breaking changes",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=evidence,
            severity="HIGH",
            metadata={
                "hypothesis_score": score,
                "evidence_sources": ["changes", "logs"],
                "failure_pattern": "deployment_issue",
                "validation_tests": [
                    "Review deployment change log and diff",
                    "Check for API contract changes",
                    "Validate configuration compatibility",
                    "Test rollback procedure"
                ]
            }
        )

    def _calculate_hypothesis_score(self, evidence: List[str], sources: List[str],
                                    findings: List[Finding], pattern: str) -> int:
        """Calculate hypothesis score (0-100)"""
        score = 0

        # Evidence strength (0-40 points)
        for finding in findings:
            if finding.confidence == ConfidenceLevel.HIGH:
                score += 10
            elif finding.confidence == ConfidenceLevel.MEDIUM:
                score += 5
            else:
                score += 2
        score = min(score, 40)

        # Evidence diversity (0-20 points)
        source_count = len(set(sources))
        if source_count >= 3:
            score += 20
        elif source_count == 2:
            score += 10
        else:
            score += 5

        # Temporal correlation (simplified - 15 points)
        score += 15

        # Pattern match (0-20 points)
        if pattern in self.FAILURE_PATTERNS:
            score += self.FAILURE_PATTERNS[pattern]["score_bonus"]

        return min(score, 100)

    def _rank_hypotheses(self, hypotheses: List[Finding]) -> List[Finding]:
        """Rank hypotheses by score"""
        return sorted(hypotheses, key=lambda h: h.metadata.get("hypothesis_score", 0), reverse=True)

    def _generate_summary(self, hypotheses: List[Finding]) -> str:
        """Generate summary"""
        if not hypotheses:
            return "Insufficient evidence to generate confident hypotheses. More investigation needed."

        top_score = hypotheses[0].metadata.get("hypothesis_score", 0)
        return f"Generated {len(hypotheses)} root cause hypotheses. " \
               f"Top hypothesis score: {top_score}/100. Validation tests provided."

    def _calculate_confidence(self, hypotheses: List[Finding]) -> ConfidenceLevel:
        """Calculate overall confidence"""
        if not hypotheses:
            return ConfidenceLevel.LOW

        top_hypothesis = hypotheses[0]
        return top_hypothesis.confidence

    def _generate_next_steps(self, hypotheses: List[Finding]) -> List[str]:
        """Generate next steps"""
        if not hypotheses:
            return [
                "Gather more diagnostic data",
                "Run additional agent analyses",
                "Check for missing evidence sources"
            ]

        # Extract validation tests from top hypothesis
        top_tests = hypotheses[0].metadata.get("validation_tests", [])
        return top_tests[:3] + ["Review lower-ranked hypotheses if top hypothesis invalid"]
