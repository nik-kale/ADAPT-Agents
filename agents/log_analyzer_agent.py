"""
Log Analyzer Agent
Analyzes system logs to identify anomalies, errors, and patterns.
"""

from typing import Dict, Any, List
from datetime import datetime
from collections import Counter, defaultdict
from schemas import (
    BaseAgent, BaseAgentInput, BaseAgentOutput,
    Finding, AgentStatus, ConfidenceLevel, AgentCapabilities
)


class LogAnalyzerAgentInput(BaseAgentInput):
    """Input schema for Log Analyzer Agent"""
    pass


class LogAnalyzerAgent(BaseAgent):
    """
    Specialized agent for analyzing system logs to identify:
    - Error patterns and recurring exceptions
    - Anomalous log behaviors
    - Temporal correlations with incidents
    - Service-level cascading failures
    """

    def __init__(self):
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

    def execute(self, input_data: BaseAgentInput) -> BaseAgentOutput:
        """
        Execute log analysis.

        Args:
            input_data: Contains logs and analysis parameters

        Returns:
            BaseAgentOutput with findings and analysis results
        """
        start_time = datetime.now()

        try:
            # Extract logs from context
            logs = input_data.context.get("logs", [])
            incident_time = input_data.context.get("incident_time")
            parameters = input_data.parameters or {}

            # Perform analysis
            findings = self._analyze_logs(logs, incident_time, parameters)

            # Generate summary
            summary = self._generate_summary(findings, len(logs))

            # Determine overall confidence
            confidence = self._calculate_confidence(findings)

            # Generate next steps
            next_steps = self._generate_next_steps(findings)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return BaseAgentOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                findings=findings,
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
                summary=f"Analysis failed: {str(e)}",
                confidence=ConfidenceLevel.UNCERTAIN,
                next_steps=["Review agent configuration", "Check input data format"],
                errors=[str(e)],
                execution_time_ms=execution_time
            )

    def _analyze_logs(self, logs: List[Dict], incident_time: str, parameters: Dict) -> List[Finding]:
        """Analyze logs and extract findings"""
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
                        "pattern": pattern
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
                        "cascade_depth": len(services)
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
