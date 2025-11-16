"""
Metrics Analyzer Agent
Analyzes time-series metrics to identify anomalies, trends, and correlations.
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime
import statistics
from schemas import (
    BaseAgent, BaseAgentInput, BaseAgentOutput,
    Finding, AgentStatus, ConfidenceLevel, AgentCapabilities
)


class MetricsAnalyzerAgent(BaseAgent):
    """
    Specialized agent for analyzing time-series metrics to identify:
    - Anomalies (spikes, drops, unusual patterns)
    - Threshold violations
    - Correlations between metrics
    - Resource saturation and trends
    """

    def __init__(self):
        capabilities = AgentCapabilities(
            name="MetricsAnalyzerAgent",
            description="Analyzes time-series metrics for anomalies, correlations, and trends",
            input_types=["metrics", "time_series"],
            output_types=["findings", "anomalies", "correlations"],
            dependencies=[],
            supports_streaming=False,
            max_context_tokens=150000
        )
        super().__init__("MetricsAnalyzerAgent", capabilities)

    def execute(self, input_data: BaseAgentInput) -> BaseAgentOutput:
        """Execute metrics analysis"""
        start_time = datetime.now()

        try:
            metrics = input_data.context.get("metrics", [])
            parameters = input_data.parameters or {}
            incident_time = input_data.context.get("incident_time")

            findings = self._analyze_metrics(metrics, incident_time, parameters)
            summary = self._generate_summary(findings, len(metrics))
            confidence = self._calculate_confidence(findings)
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
                next_steps=["Review metrics data format", "Check parameter configuration"],
                errors=[str(e)],
                execution_time_ms=execution_time
            )

    def _analyze_metrics(self, metrics: List[Dict], incident_time: str, parameters: Dict) -> List[Finding]:
        """Analyze metrics and extract findings"""
        findings = []
        anomaly_threshold = parameters.get("anomaly_threshold", 3.0)

        # 1. Anomaly detection
        for metric in metrics:
            anomaly_findings = self._detect_anomalies(metric, anomaly_threshold)
            findings.extend(anomaly_findings)

        # 2. Threshold violations
        threshold_findings = self._detect_threshold_violations(metrics)
        findings.extend(threshold_findings)

        # 3. Correlation analysis
        if len(metrics) >= 2:
            correlation_findings = self._detect_correlations(metrics, parameters)
            findings.extend(correlation_findings)

        # 4. Trend analysis
        trend_findings = self._detect_trends(metrics)
        findings.extend(trend_findings)

        # Prioritize and limit
        findings = self._prioritize_findings(findings)
        return findings[:10]

    def _detect_anomalies(self, metric: Dict, threshold: float) -> List[Finding]:
        """Detect statistical anomalies in a metric"""
        findings = []
        values = metric.get("values", [])

        if len(values) < 10:
            return findings

        try:
            mean = statistics.mean(values)
            stdev = statistics.stdev(values)

            if stdev == 0:
                return findings

            # Find values with high z-scores
            anomalies = []
            for i, value in enumerate(values):
                z_score = abs((value - mean) / stdev)
                if z_score >= threshold:
                    timestamps = metric.get("timestamps", [])
                    timestamp = timestamps[i] if i < len(timestamps) else None
                    anomalies.append({
                        "value": value,
                        "z_score": z_score,
                        "timestamp": timestamp,
                        "index": i
                    })

            # Create finding if anomalies found
            if anomalies:
                metric_name = metric.get("name", "unknown")
                service = metric.get("service", "unknown")
                unit = metric.get("unit", "")

                max_anomaly = max(anomalies, key=lambda x: x["z_score"])
                deviation_pct = ((max_anomaly["value"] - mean) / mean * 100) if mean != 0 else 0

                finding = Finding(
                    type="anomaly",
                    description=f"{metric_name} on {service} showed {len(anomalies)} anomalous values "
                               f"(peak: {max_anomaly['value']:.2f}{unit}, baseline: {mean:.2f}±{stdev:.2f}{unit})",
                    confidence=ConfidenceLevel.HIGH if max_anomaly["z_score"] >= 5 else ConfidenceLevel.MEDIUM,
                    evidence=[
                        f"Peak value: {max_anomaly['value']:.2f}{unit} (z-score: {max_anomaly['z_score']:.2f})",
                        f"Baseline: {mean:.2f} ± {stdev:.2f}{unit}",
                        f"Deviation: {deviation_pct:+.1f}%",
                        f"{len(anomalies)} anomalous data points detected"
                    ],
                    severity="CRITICAL" if max_anomaly["z_score"] >= 5 else "HIGH",
                    timestamp=max_anomaly.get("timestamp"),
                    metadata={
                        "affected_metrics": [metric_name],
                        "service": service,
                        "peak_value": max_anomaly["value"],
                        "baseline_mean": mean,
                        "baseline_stddev": stdev,
                        "deviation_percent": deviation_pct,
                        "z_score": max_anomaly["z_score"],
                        "anomaly_count": len(anomalies)
                    }
                )
                findings.append(finding)

        except statistics.StatisticsError:
            pass

        return findings

    def _detect_threshold_violations(self, metrics: List[Dict]) -> List[Finding]:
        """Detect metrics exceeding operational thresholds"""
        findings = []

        # Define common thresholds
        thresholds = {
            "cpu_usage": 80,
            "memory_usage": 90,
            "disk_usage": 85,
            "error_rate": 1,
            "p99_latency": 1000  # ms
        }

        for metric in metrics:
            metric_name = metric.get("name", "")
            values = metric.get("values", [])

            # Check if metric has a known threshold
            threshold = thresholds.get(metric_name)
            if threshold and values:
                violations = [v for v in values if v > threshold]

                if violations:
                    service = metric.get("service", "unknown")
                    unit = metric.get("unit", "")
                    max_value = max(violations)
                    violation_pct = (len(violations) / len(values)) * 100

                    finding = Finding(
                        type="threshold_violation",
                        description=f"{metric_name} on {service} exceeded threshold "
                                   f"({max_value:.1f}{unit} > {threshold}{unit}) "
                                   f"for {violation_pct:.0f}% of period",
                        confidence=ConfidenceLevel.HIGH,
                        evidence=[
                            f"Threshold: {threshold}{unit}",
                            f"Peak value: {max_value:.1f}{unit}",
                            f"Violations: {len(violations)}/{len(values)} data points"
                        ],
                        severity="CRITICAL" if violation_pct > 50 else "HIGH",
                        metadata={
                            "affected_metrics": [metric_name],
                            "service": service,
                            "threshold": threshold,
                            "actual_value": max_value,
                            "violation_percent": violation_pct
                        }
                    )
                    findings.append(finding)

        return findings

    def _detect_correlations(self, metrics: List[Dict], parameters: Dict) -> List[Finding]:
        """Detect correlations between metrics"""
        findings = []
        min_correlation = parameters.get("correlation_min", 0.7)

        # Simplified correlation detection
        # Real implementation would use proper correlation algorithms
        # For now, just detect inverse throughput/latency relationship

        throughput_metrics = [m for m in metrics if "throughput" in m.get("name", "").lower()]
        latency_metrics = [m for m in metrics if "latency" in m.get("name", "").lower()]

        if throughput_metrics and latency_metrics:
            # Simplified: check if throughput decreased while latency increased
            for t_metric in throughput_metrics[:1]:
                for l_metric in latency_metrics[:1]:
                    t_values = t_metric.get("values", [])
                    l_values = l_metric.get("values", [])

                    if len(t_values) >= 2 and len(l_values) >= 2:
                        t_change = ((t_values[-1] - t_values[0]) / t_values[0] * 100) if t_values[0] != 0 else 0
                        l_change = ((l_values[-1] - l_values[0]) / l_values[0] * 100) if l_values[0] != 0 else 0

                        # If throughput down and latency up (inverse correlation)
                        if t_change < -20 and l_change > 50:
                            finding = Finding(
                                type="correlation",
                                description=f"Inverse correlation detected: throughput decreased {abs(t_change):.0f}% "
                                           f"while latency increased {l_change:.0f}%",
                                confidence=ConfidenceLevel.HIGH,
                                evidence=[
                                    f"Throughput: {t_values[0]:.0f} → {t_values[-1]:.0f} ({t_change:+.0f}%)",
                                    f"Latency: {l_values[0]:.0f}ms → {l_values[-1]:.0f}ms ({l_change:+.0f}%)",
                                    "Pattern indicates performance degradation"
                                ],
                                severity="HIGH",
                                metadata={
                                    "affected_metrics": [t_metric.get("name"), l_metric.get("name")],
                                    "correlation_type": "inverse",
                                    "metric_changes": {
                                        t_metric.get("name"): t_change,
                                        l_metric.get("name"): l_change
                                    }
                                }
                            )
                            findings.append(finding)

        return findings

    def _detect_trends(self, metrics: List[Dict]) -> List[Finding]:
        """Detect concerning trends in metrics"""
        findings = []

        for metric in metrics:
            values = metric.get("values", [])
            if len(values) < 5:
                continue

            # Check for saturation (sustained high values)
            if len(values) >= 5:
                recent = values[-5:]
                if all(v >= 95 for v in recent):
                    metric_name = metric.get("name", "unknown")
                    service = metric.get("service", "unknown")
                    unit = metric.get("unit", "")

                    finding = Finding(
                        type="trend",
                        description=f"{metric_name} on {service} saturated at ~{recent[0]:.0f}{unit} "
                                   f"(sustained high level detected)",
                        confidence=ConfidenceLevel.MEDIUM,
                        evidence=[
                            f"Last 5 values: {', '.join(f'{v:.0f}{unit}' for v in recent)}",
                            "Pattern indicates resource saturation"
                        ],
                        severity="HIGH",
                        metadata={
                            "affected_metrics": [metric_name],
                            "service": service,
                            "pattern": "saturation",
                            "sustained_value": recent[0]
                        }
                    )
                    findings.append(finding)

        return findings

    def _prioritize_findings(self, findings: List[Finding]) -> List[Finding]:
        """Sort findings by severity and confidence"""
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        confidence_order = {ConfidenceLevel.HIGH: 0, ConfidenceLevel.MEDIUM: 1,
                          ConfidenceLevel.LOW: 2, ConfidenceLevel.UNCERTAIN: 3}

        return sorted(findings,
                     key=lambda f: (severity_order.get(f.severity, 99),
                                   confidence_order.get(f.confidence, 99)))

    def _generate_summary(self, findings: List[Finding], total_metrics: int) -> str:
        """Generate summary of analysis"""
        if not findings:
            return f"Analyzed {total_metrics} metrics. All metrics within normal ranges."

        anomalies = sum(1 for f in findings if f.type == "anomaly")
        thresholds = sum(1 for f in findings if f.type == "threshold_violation")
        correlations = sum(1 for f in findings if f.type == "correlation")

        return f"Analyzed {total_metrics} metrics. Found {anomalies} anomalies, " \
               f"{thresholds} threshold violations, {correlations} correlations."

    def _calculate_confidence(self, findings: List[Finding]) -> ConfidenceLevel:
        """Calculate overall confidence"""
        if not findings:
            return ConfidenceLevel.MEDIUM

        high_conf = sum(1 for f in findings if f.confidence == ConfidenceLevel.HIGH)
        if high_conf >= len(findings) * 0.6:
            return ConfidenceLevel.HIGH
        elif high_conf >= len(findings) * 0.3:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def _generate_next_steps(self, findings: List[Finding]) -> List[str]:
        """Generate recommended next steps"""
        if not findings:
            return ["Continue monitoring metrics for trends"]

        steps = []
        has_cpu = any("cpu" in f.description.lower() for f in findings)
        has_memory = any("memory" in f.description.lower() for f in findings)
        has_latency = any("latency" in f.description.lower() for f in findings)

        if has_cpu or has_memory:
            steps.append("Investigate resource-intensive processes or memory leaks")
        if has_latency:
            steps.append("Analyze request traces and database query performance")

        steps.append("Correlate metrics with log events and deployments")
        steps.append("Check for recent configuration or code changes")

        return steps
