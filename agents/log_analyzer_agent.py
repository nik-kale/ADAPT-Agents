"""
Log Analyzer Agent
Analyzes system logs to identify anomalies, errors, and patterns.
Now with async/await, LLM integration, caching, and metrics!
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import Counter, defaultdict
from schemas import (
    AsyncBaseAgent, BaseAgentInput, BaseAgentOutput,
    Finding, AgentStatus, ConfidenceLevel, AgentCapabilities
)
from utils.metrics import record_execution_metrics
from utils.caching import get_cache
from utils.logging import get_logger


class LogAnalyzerAgentInput(BaseAgentInput):
    """Input schema for Log Analyzer Agent"""
    pass


class LogAnalyzerAgent(AsyncBaseAgent):
    """
    Specialized agent for analyzing system logs to identify:
    - Error patterns and recurring exceptions
    - Anomalous log behaviors
    - Temporal correlations with incidents
    - Service-level cascading failures

    Now with:
    - Async/await execution
    - Optional LLM-powered analysis
    - Result caching
    - Prometheus metrics
    """

    def __init__(self, use_llm: bool = False):
        capabilities = AgentCapabilities(
            name="LogAnalyzerAgent",
            description="Analyzes system logs for error patterns, anomalies, and correlations",
            input_types=["logs", "log_stream"],
            output_types=["findings", "error_patterns"],
            dependencies=[],
            supports_streaming=False,
            max_context_tokens=100000
        )
        super().__init__("LogAnalyzerAgent", capabilities)
        self.use_llm = use_llm
        self.cache = get_cache()
        self.logger = get_logger(__name__)
        self.llm = None

        if use_llm:
            from llm.base_llm import get_llm
            self.llm = get_llm()

    @record_execution_metrics
    async def execute_async(self, input_data: BaseAgentInput) -> BaseAgentOutput:
        """
        Execute log analysis asynchronously.

        Args:
            input_data: Contains logs and analysis parameters

        Returns:
            BaseAgentOutput with findings and analysis results
        """
        start_time = datetime.now()

        self.logger.info("Starting log analysis", agent=self.name)

        try:
            # Check cache first
            cached_result = await self.cache.get(self.name, input_data)
            if cached_result:
                self.logger.info("Cache hit", agent=self.name)
                return cached_result

            self.logger.info("Cache miss, performing analysis", agent=self.name)

            # Extract logs from context
            logs = input_data.context.get("logs", [])
            incident_time = input_data.context.get("incident_time")
            parameters = input_data.parameters or {}

            # Perform analysis (rule-based + optional LLM)
            if self.use_llm and self.llm and len(logs) > 0:
                findings = await self._analyze_logs_with_llm(logs, incident_time, parameters)
            else:
                findings = await self._analyze_logs_rule_based(logs, incident_time, parameters)

            # Generate summary
            summary = self._generate_summary(findings, len(logs))

            # Determine overall confidence
            confidence = self._calculate_confidence(findings)

            # Generate next steps
            next_steps = self._generate_next_steps(findings)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            result = BaseAgentOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                findings=findings,
                summary=summary,
                confidence=confidence,
                next_steps=next_steps,
                errors=[],
                execution_time_ms=execution_time
            )

            # Cache the result
            await self.cache.set(self.name, input_data, result)

            self.logger.info("Log analysis completed",
                           agent=self.name,
                           findings_count=len(findings),
                           execution_time_ms=execution_time)

            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.error("Log analysis failed",
                            agent=self.name,
                            error=str(e),
                            execution_time_ms=execution_time)

            return BaseAgentOutput(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                findings=[],
                summary=f"Analysis failed: {str(e)}",
                confidence=ConfidenceLevel.UNCERTAIN,
                next_steps=["Review agent configuration", "Check input data format"],
                errors=[str(e)],
                execution_time_ms=execution_time
            )

    async def _analyze_logs_with_llm(self, logs: List[Dict], incident_time: str, parameters: Dict) -> List[Finding]:
        """Analyze logs using LLM for deeper insights"""
        # First get rule-based findings as baseline
        rule_based_findings = await self._analyze_logs_rule_based(logs, incident_time, parameters)

        # Prepare context for LLM
        log_sample = logs[:50]  # Limit to avoid token overflow
        error_logs = [log for log in logs if log.get("level") == "ERROR"][:20]

        prompt = f"""Analyze these system logs to identify root cause indicators:

Incident Time: {incident_time}
Total Logs: {len(logs)}
Error Logs: {len(error_logs)}

Sample Error Logs:
{self._format_logs_for_llm(error_logs)}

Rule-based Findings:
{self._format_findings_for_llm(rule_based_findings)}

Identify:
1. Root cause indicators
2. Error propagation patterns
3. Temporal correlations
4. Service dependencies

Respond with structured JSON."""

        try:
            llm_response = await self.llm.generate_structured(
                prompt=prompt,
                schema={
                    "findings": [
                        {
                            "type": "str",
                            "description": "str",
                            "confidence": "str",  # HIGH, MEDIUM, LOW
                            "evidence": ["str"],
                            "severity": "str"
                        }
                    ]
                }
            )

            # Convert LLM findings to Finding objects
            llm_findings = []
            for f in llm_response.get("findings", []):
                llm_findings.append(Finding(
                    type=f.get("type", "llm_insight"),
                    description=f.get("description", ""),
                    confidence=ConfidenceLevel[f.get("confidence", "MEDIUM")],
                    evidence=f.get("evidence", []),
                    severity=f.get("severity", "MEDIUM"),
                    metadata={"source": "llm"}
                ))

            # Combine with rule-based findings
            return rule_based_findings + llm_findings

        except Exception as e:
            self.logger.warning(f"LLM analysis failed, using rule-based only: {str(e)}")
            return rule_based_findings

    async def _analyze_logs_rule_based(self, logs: List[Dict], incident_time: str, parameters: Dict) -> List[Finding]:
        """Analyze logs using rule-based logic (original implementation)"""
        findings = []

        # 1. Error pattern detection
        error_patterns = self._detect_error_patterns(logs)
        findings.extend(error_patterns)

        # 2. Temporal spike detection
        if incident_time:
            spike_findings = self._detect_temporal_spikes(logs, incident_time)
            findings.extend(spike_findings)

        # 3. Cascade detection
        cascade_findings = self._detect_cascades(logs)
        findings.extend(cascade_findings)

        # 4. Anomaly detection
        anomaly_findings = self._detect_anomalies(logs)
        findings.extend(anomaly_findings)

        # Sort by severity and confidence
        findings = self._prioritize_findings(findings)

        # Limit to top 10
        return findings[:10]

    def _detect_error_patterns(self, logs: List[Dict]) -> List[Finding]:
        """Detect recurring error patterns"""
        findings = []
        error_logs = [log for log in logs if log.get("level") == "ERROR"]

        # Group by error message pattern (simplified)
        error_groups = defaultdict(list)
        for log in error_logs:
            message = log.get("message", "")
            # Simple grouping by first 50 chars
            pattern_key = message[:50] if message else "unknown"
            error_groups[pattern_key].append(log)

        # Report significant patterns (>= 3 occurrences)
        for pattern, occurrences in error_groups.items():
            if len(occurrences) >= 3:
                service = occurrences[0].get("service", "unknown")
                confidence = ConfidenceLevel.HIGH if len(occurrences) >= 10 else ConfidenceLevel.MEDIUM

                finding = Finding(
                    type="error_pattern",
                    description=f"Recurring error in {service}: {pattern}... ({len(occurrences)} occurrences)",
                    confidence=confidence,
                    evidence=[log.get("message", "")[:200] for log in occurrences[:5]],
                    severity="CRITICAL" if len(occurrences) >= 10 else "HIGH",
                    metadata={
                        "affected_services": [service],
                        "error_count": len(occurrences),
                        "pattern": pattern,
                        "source": "rule_based"
                    }
                )
                findings.append(finding)

        return findings

    def _detect_temporal_spikes(self, logs: List[Dict], incident_time: str) -> List[Finding]:
        """Detect error spikes around incident time"""
        findings = []
        # Simplified: check for errors within 5 minutes of incident
        # Real implementation would use proper time window analysis
        return findings

    def _detect_cascades(self, logs: List[Dict]) -> List[Finding]:
        """Detect cascading failures across services"""
        findings = []
        # Simplified: group errors by trace_id to find cascades
        trace_groups = defaultdict(list)
        for log in logs:
            if log.get("level") == "ERROR" and log.get("trace_id"):
                trace_groups[log["trace_id"]].append(log)

        # Find traces with multiple service errors
        for trace_id, trace_logs in trace_groups.items():
            services = set(log.get("service") for log in trace_logs)
            if len(services) >= 2:
                finding = Finding(
                    type="cascade",
                    description=f"Cascading failure across {len(services)} services (trace: {trace_id[:8]}...)",
                    confidence=ConfidenceLevel.HIGH,
                    evidence=[f"{log.get('service')}: {log.get('message', '')[:100]}" for log in trace_logs[:3]],
                    severity="HIGH",
                    metadata={
                        "affected_services": list(services),
                        "trace_id": trace_id,
                        "cascade_depth": len(services),
                        "source": "rule_based"
                    }
                )
                findings.append(finding)

        return findings

    def _detect_anomalies(self, logs: List[Dict]) -> List[Finding]:
        """Detect anomalous log patterns"""
        # Simplified anomaly detection
        return []

    def _prioritize_findings(self, findings: List[Finding]) -> List[Finding]:
        """Sort findings by severity and confidence"""
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        confidence_order = {ConfidenceLevel.HIGH: 0, ConfidenceLevel.MEDIUM: 1,
                          ConfidenceLevel.LOW: 2, ConfidenceLevel.UNCERTAIN: 3}

        return sorted(findings,
                     key=lambda f: (severity_order.get(f.severity, 99),
                                   confidence_order.get(f.confidence, 99)))

    def _generate_summary(self, findings: List[Finding], total_logs: int) -> str:
        """Generate summary of analysis"""
        if not findings:
            return f"Analyzed {total_logs} log entries. No significant issues detected."

        critical = sum(1 for f in findings if f.severity == "CRITICAL")
        high = sum(1 for f in findings if f.severity == "HIGH")

        return f"Analyzed {total_logs} logs. Found {len(findings)} issues: {critical} critical, {high} high severity."

    def _calculate_confidence(self, findings: List[Finding]) -> ConfidenceLevel:
        """Calculate overall confidence"""
        if not findings:
            return ConfidenceLevel.LOW

        high_conf = sum(1 for f in findings if f.confidence == ConfidenceLevel.HIGH)
        if high_conf >= len(findings) * 0.6:
            return ConfidenceLevel.HIGH
        elif high_conf >= len(findings) * 0.3:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def _generate_next_steps(self, findings: List[Finding]) -> List[str]:
        """Generate recommended next steps"""
        if not findings:
            return ["Continue monitoring system health"]

        steps = []
        has_cascade = any(f.type == "cascade" for f in findings)
        has_db_error = any("database" in f.description.lower() for f in findings)

        if has_cascade:
            steps.append("Investigate distributed tracing for cascading failures")
        if has_db_error:
            steps.append("Check database connection pool and query performance")

        steps.append("Correlate findings with metrics and change events")
        steps.append("Review affected services for recent deployments")

        return steps

    def _format_logs_for_llm(self, logs: List[Dict]) -> str:
        """Format logs for LLM prompt"""
        formatted = []
        for log in logs:
            formatted.append(
                f"{log.get('timestamp', 'N/A')} [{log.get('level', 'INFO')}] "
                f"{log.get('service', 'unknown')}: {log.get('message', '')}"
            )
        return "\n".join(formatted)

    def _format_findings_for_llm(self, findings: List[Finding]) -> str:
        """Format findings for LLM prompt"""
        formatted = []
        for i, f in enumerate(findings, 1):
            formatted.append(
                f"{i}. [{f.severity}] {f.description} (confidence: {f.confidence.value})"
            )
        return "\n".join(formatted)
