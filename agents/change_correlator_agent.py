"""
Change Correlator Agent
Correlates change events with incidents to identify potential root causes.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from schemas import (
    BaseAgent, BaseAgentInput, BaseAgentOutput,
    Finding, AgentStatus, ConfidenceLevel, AgentCapabilities
)


class ChangeCorrelatorAgent(BaseAgent):
    """
    Specialized agent for correlating change events with incidents:
    - Temporal correlation of changes and incidents
    - Change risk assessment
    - Blast radius determination
    - Service impact mapping
    """

    def __init__(self):
        capabilities = AgentCapabilities(
            name="ChangeCorrelatorAgent",
            description="Correlates change events with incidents to identify root causes",
            input_types=["changes", "change_events"],
            output_types=["findings", "correlations"],
            dependencies=[],
            supports_streaming=False
        )
        super().__init__("ChangeCorrelatorAgent", capabilities)

    def execute(self, input_data: BaseAgentInput) -> BaseAgentOutput:
        """Execute change correlation analysis"""
        start_time = datetime.now()

        try:
            changes = input_data.context.get("changes", [])
            incident_time = input_data.context.get("incident_time")
            affected_services = input_data.context.get("affected_services", [])
            parameters = input_data.parameters or {}

            findings = self._correlate_changes(changes, incident_time, affected_services, parameters)
            summary = self._generate_summary(findings, len(changes))
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
                next_steps=["Review change event data", "Verify incident timestamp"],
                errors=[str(e)],
                execution_time_ms=execution_time
            )

    def _correlate_changes(self, changes: List[Dict], incident_time: str,
                          affected_services: List[str], parameters: Dict) -> List[Finding]:
        """Correlate changes with incident"""
        findings = []
        correlation_window = parameters.get("correlation_window_minutes", 60)

        if not incident_time:
            return findings

        try:
            incident_dt = datetime.fromisoformat(incident_time.replace('Z', '+00:00'))
        except:
            # Fallback parsing
            incident_dt = datetime.now()

        # Filter changes within correlation window
        relevant_changes = []
        for change in changes:
            try:
                change_dt = datetime.fromisoformat(change.get("timestamp", "").replace('Z', '+00:00'))
                time_delta = (incident_dt - change_dt).total_seconds() / 60

                # Change occurred before incident and within window
                if 0 <= time_delta <= correlation_window:
                    change["time_to_incident_minutes"] = time_delta
                    relevant_changes.append(change)
            except:
                continue

        # Score and analyze each relevant change
        for change in relevant_changes:
            risk_score = self._calculate_risk_score(change, affected_services)

            if risk_score >= 40:  # Minimum threshold
                finding = self._create_change_finding(change, risk_score, affected_services)
                findings.append(finding)

        # Detect concurrent changes pattern
        if len(relevant_changes) >= 3:
            concurrent_finding = self._create_concurrent_changes_finding(relevant_changes)
            findings.append(concurrent_finding)

        # Sort by risk score and limit
        findings.sort(key=lambda f: f.metadata.get("risk_score", 0), reverse=True)
        return findings[:10]

    def _calculate_risk_score(self, change: Dict, affected_services: List[str]) -> int:
        """Calculate risk score for a change"""
        score = 0

        # Temporal proximity (0-30 points)
        time_delta = change.get("time_to_incident_minutes", 999)
        if time_delta < 5:
            score += 30
        elif time_delta < 15:
            score += 25
        elif time_delta < 30:
            score += 20
        elif time_delta < 60:
            score += 10
        else:
            score += 5

        # Service relevance (0-30 points)
        change_service = change.get("service", "")
        if change_service in affected_services:
            score += 30  # Direct match
        elif any(svc in change_service or change_service in svc for svc in affected_services):
            score += 20  # Partial match
        else:
            score += 5  # Potential shared infrastructure

        # Change type (0-20 points)
        change_type = change.get("type", "")
        type_scores = {
            "rollback": 25,
            "deployment": 20,
            "config_change": 15,
            "infrastructure": 10
        }
        score += type_scores.get(change_type, 5)

        # Change magnitude (0-20 points)
        # Simplified: check version numbers if available
        metadata = change.get("metadata", {})
        version = metadata.get("version", "")
        if "major" in version.lower() or version.startswith("2."):
            score += 20
        elif "minor" in version.lower() or version.count('.') >= 2:
            score += 15
        else:
            score += 10

        return min(score, 100)

    def _create_change_finding(self, change: Dict, risk_score: int, affected_services: List[str]) -> Finding:
        """Create a finding for a correlated change"""
        change_type = change.get("type", "change")
        service = change.get("service", "unknown")
        description = change.get("description", "")
        time_delta = change.get("time_to_incident_minutes", 0)

        # Determine severity based on risk score
        if risk_score >= 80:
            severity = "CRITICAL"
            confidence = ConfidenceLevel.HIGH
        elif risk_score >= 60:
            severity = "HIGH"
            confidence = ConfidenceLevel.HIGH
        else:
            severity = "MEDIUM"
            confidence = ConfidenceLevel.MEDIUM

        evidence = [
            f"Change type: {change_type}",
            f"Service: {service}",
            f"Time to incident: {time_delta:.0f} minutes",
            f"Risk score: {risk_score}/100"
        ]

        if description:
            evidence.append(f"Description: {description}")

        metadata = change.get("metadata", {})
        if metadata.get("version"):
            evidence.append(f"Version: {metadata.get('version')}")

        # Determine blast radius
        blast_radius = "single_service"
        if service in affected_services:
            if len(affected_services) > 1:
                blast_radius = "multiple_services"
        else:
            blast_radius = "infrastructure"

        finding_desc = f"{change_type} on {service} occurred {time_delta:.0f} minutes before incident"
        if risk_score >= 80:
            finding_desc += " (HIGH RISK)"

        return Finding(
            type="correlated_change",
            description=finding_desc,
            confidence=confidence,
            evidence=evidence,
            severity=severity,
            timestamp=change.get("timestamp"),
            metadata={
                "change_id": change.get("id", ""),
                "change_type": change_type,
                "time_to_incident_minutes": time_delta,
                "risk_score": risk_score,
                "affected_services": [service],
                "blast_radius": blast_radius,
                **metadata
            }
        )

    def _create_concurrent_changes_finding(self, changes: List[Dict]) -> Finding:
        """Create finding for concurrent changes pattern"""
        services = list(set(c.get("service", "unknown") for c in changes))
        time_window = max(c.get("time_to_incident_minutes", 0) for c in changes)

        evidence = [
            f"{len(changes)} changes within {time_window:.0f} minute window:",
        ]
        for change in changes[:5]:
            evidence.append(f"  - {change.get('service')}: {change.get('type')} at T-{change.get('time_to_incident_minutes', 0):.0f}min")

        return Finding(
            type="concurrent_changes",
            description=f"{len(changes)} concurrent changes detected in {time_window:.0f} minute window (unusual pattern)",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=evidence,
            severity="MEDIUM",
            metadata={
                "change_type": "concurrent_changes",
                "change_count": len(changes),
                "time_window_minutes": time_window,
                "affected_services": services
            }
        )

    def _generate_summary(self, findings: List[Finding], total_changes: int) -> str:
        """Generate summary"""
        if not findings:
            return f"Analyzed {total_changes} changes. No significant correlations found."

        high_risk = sum(1 for f in findings if f.metadata.get("risk_score", 0) >= 80)
        return f"Analyzed {total_changes} changes. Found {len(findings)} correlations, {high_risk} high-risk."

    def _calculate_confidence(self, findings: List[Finding]) -> ConfidenceLevel:
        """Calculate overall confidence"""
        if not findings:
            return ConfidenceLevel.LOW

        high_conf = sum(1 for f in findings if f.confidence == ConfidenceLevel.HIGH)
        if high_conf >= 1:
            return ConfidenceLevel.HIGH
        return ConfidenceLevel.MEDIUM

    def _generate_next_steps(self, findings: List[Finding]) -> List[str]:
        """Generate next steps"""
        if not findings:
            return ["No change-related root cause identified", "Investigate other factors"]

        steps = ["Review high-risk changes for rollback feasibility"]

        has_deployment = any(f.metadata.get("change_type") == "deployment" for f in findings)
        has_config = any(f.metadata.get("change_type") == "config_change" for f in findings)

        if has_deployment:
            steps.append("Compare code diff between versions")
        if has_config:
            steps.append("Review configuration changes and validate values")

        steps.append("Coordinate with change authors for additional context")

        return steps
