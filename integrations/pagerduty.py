"""
PagerDuty Integration
Creates and manages incidents in PagerDuty
"""

from typing import Dict, Any, Optional, List
import httpx
import json
from datetime import datetime


class PagerDutyIntegration:
    """
    PagerDuty integration for incident management

    Features:
    - Create PagerDuty incidents
    - Trigger alerts
    - Add notes to incidents
    - Resolve incidents
    - Update incident priority
    - Acknowledge incidents
    """

    def __init__(
        self,
        api_key: str,
        integration_key: Optional[str] = None,
        from_email: Optional[str] = None
    ):
        """
        Initialize PagerDuty integration

        Args:
            api_key: PagerDuty REST API key
            integration_key: Events API integration key (for triggering alerts)
            from_email: Email of user creating incidents (required for REST API)
        """
        self.api_key = api_key
        self.integration_key = integration_key
        self.from_email = from_email
        self.api_base = "https://api.pagerduty.com"
        self.events_base = "https://events.pagerduty.com"

    async def trigger_incident(
        self,
        incident_id: str,
        incident_data: Dict[str, Any],
        service_id: Optional[str] = None,
        escalation_policy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger incident in PagerDuty via Events API

        Args:
            incident_id: Unique incident identifier (dedup key)
            incident_data: Incident details
            service_id: PagerDuty service ID (if using REST API)
            escalation_policy_id: Escalation policy ID

        Returns:
            PagerDuty response
        """
        if not self.integration_key:
            raise ValueError("integration_key required for triggering incidents")

        # Build severity mapping
        severity_map = {
            "critical": "critical",
            "high": "error",
            "medium": "warning",
            "low": "info"
        }
        severity = severity_map.get(incident_data.get("severity", "medium").lower(), "warning")

        # Build summary
        services = ", ".join(incident_data.get("affected_services", []))
        summary = f"Incident in {services}" if services else "System Incident"

        # Build custom details
        custom_details = {
            "incident_id": incident_id,
            "incident_time": incident_data.get("incident_time", "Unknown"),
            "affected_services": incident_data.get("affected_services", []),
            "severity": incident_data.get("severity", "unknown")
        }

        # Add error logs if available
        if "logs" in incident_data and incident_data["logs"]:
            error_logs = [log for log in incident_data["logs"] if log.get("level") == "ERROR"][:5]
            if error_logs:
                custom_details["recent_errors"] = [log.get("message", "") for log in error_logs]

        # Build payload
        payload = {
            "routing_key": self.integration_key,
            "event_action": "trigger",
            "dedup_key": incident_id,
            "payload": {
                "summary": summary,
                "severity": severity,
                "source": "ADAPT-Agents",
                "timestamp": datetime.utcnow().isoformat(),
                "custom_details": custom_details
            }
        }

        # Send event
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.events_base}/v2/enqueue",
                json=payload,
                timeout=30
            )

            if response.status_code == 202:
                return {
                    "success": True,
                    "dedup_key": incident_id,
                    "message": "Incident triggered in PagerDuty"
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }

    async def create_incident(
        self,
        incident_id: str,
        incident_data: Dict[str, Any],
        service_id: str,
        escalation_policy_id: Optional[str] = None,
        urgency: str = "high"
    ) -> Dict[str, Any]:
        """
        Create incident via REST API (more control than Events API)

        Args:
            incident_id: Incident identifier
            incident_data: Incident details
            service_id: PagerDuty service ID
            escalation_policy_id: Optional escalation policy
            urgency: 'high' or 'low'

        Returns:
            Created incident details
        """
        if not self.from_email:
            raise ValueError("from_email required for creating incidents via REST API")

        # Build title
        services = ", ".join(incident_data.get("affected_services", []))
        title = f"[{incident_id}] Incident in {services}" if services else f"[{incident_id}] System Incident"

        # Build body details
        body_parts = [
            f"Incident ID: {incident_id}",
            f"Time: {incident_data.get('incident_time', 'Unknown')}",
            f"Severity: {incident_data.get('severity', 'Unknown')}",
            f"Affected Services: {services or 'None specified'}"
        ]

        body = {"type": "incident_body", "details": "\n".join(body_parts)}

        # Build payload
        payload = {
            "incident": {
                "type": "incident",
                "title": title,
                "service": {"id": service_id, "type": "service_reference"},
                "urgency": urgency,
                "body": body,
                "incident_key": incident_id  # Dedup key
            }
        }

        if escalation_policy_id:
            payload["incident"]["escalation_policy"] = {
                "id": escalation_policy_id,
                "type": "escalation_policy_reference"
            }

        # Create incident
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/incidents",
                headers={
                    "Authorization": f"Token token={self.api_key}",
                    "From": self.from_email,
                    "Content-Type": "application/json",
                    "Accept": "application/vnd.pagerduty+json;version=2"
                },
                json=payload,
                timeout=30
            )

            if response.status_code == 201:
                result = response.json()
                incident = result.get("incident", {})
                return {
                    "success": True,
                    "incident_id": incident.get("id"),
                    "incident_number": incident.get("incident_number"),
                    "html_url": incident.get("html_url"),
                    "status": incident.get("status")
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }

    async def add_note(
        self,
        incident_id: str,
        note_content: str
    ) -> Dict[str, Any]:
        """
        Add note to PagerDuty incident

        Args:
            incident_id: PagerDuty incident ID (not dedup key)
            note_content: Note text

        Returns:
            Note creation response
        """
        if not self.from_email:
            raise ValueError("from_email required for adding notes")

        payload = {
            "note": {
                "content": note_content
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/incidents/{incident_id}/notes",
                headers={
                    "Authorization": f"Token token={self.api_key}",
                    "From": self.from_email,
                    "Content-Type": "application/json",
                    "Accept": "application/vnd.pagerduty+json;version=2"
                },
                json=payload,
                timeout=30
            )

            if response.status_code == 201:
                return {"success": True, "note": response.json()}
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }

    async def add_rca_note(
        self,
        incident_id: str,
        rca_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add RCA results as note to PagerDuty incident

        Args:
            incident_id: PagerDuty incident ID
            rca_results: Complete RCA results

        Returns:
            Note creation response
        """
        # Format RCA results as note
        note_parts = ["=== Root Cause Analysis Complete ===\n"]

        # Add hypothesis
        if "phase2" in rca_results and "hypothesis_generator" in rca_results["phase2"]:
            hyp = rca_results["phase2"]["hypothesis_generator"]
            if hasattr(hyp, "findings") and hyp.findings:
                note_parts.append("ROOT CAUSE:")
                for idx, finding in enumerate(hyp.findings[:3], 1):
                    finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                    note_parts.append(f"{idx}. {finding_dict.get('description', 'N/A')}")
                    if "confidence" in finding_dict:
                        note_parts.append(f"   Confidence: {finding_dict['confidence']}")
                note_parts.append("")

        # Add remediation
        if "phase3" in rca_results and "remediation_planner" in rca_results["phase3"]:
            rem = rca_results["phase3"]["remediation_planner"]
            if hasattr(rem, "findings") and rem.findings:
                note_parts.append("RECOMMENDED ACTIONS:")
                for idx, finding in enumerate(rem.findings[:3], 1):
                    finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                    note_parts.append(f"{idx}. {finding_dict.get('description', 'N/A')}")
                    if "priority" in finding_dict:
                        note_parts.append(f"   Priority: {finding_dict['priority']}")
                note_parts.append("")

        # Add execution time
        if "execution_time_ms" in rca_results:
            exec_time_sec = rca_results["execution_time_ms"] / 1000
            note_parts.append(f"Analysis completed in {exec_time_sec:.2f}s")

        note_content = "\n".join(note_parts)
        return await self.add_note(incident_id, note_content)

    async def resolve_incident(
        self,
        incident_id: str,
        resolution: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve PagerDuty incident via Events API

        Args:
            incident_id: Dedup key
            resolution: Optional resolution note

        Returns:
            Resolution response
        """
        if not self.integration_key:
            raise ValueError("integration_key required for resolving incidents")

        payload = {
            "routing_key": self.integration_key,
            "event_action": "resolve",
            "dedup_key": incident_id
        }

        if resolution:
            payload["payload"] = {"summary": resolution}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.events_base}/v2/enqueue",
                json=payload,
                timeout=30
            )

            if response.status_code == 202:
                return {"success": True, "message": "Incident resolved"}
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }

    async def acknowledge_incident(
        self,
        incident_id: str
    ) -> Dict[str, Any]:
        """
        Acknowledge PagerDuty incident via Events API

        Args:
            incident_id: Dedup key

        Returns:
            Acknowledgment response
        """
        if not self.integration_key:
            raise ValueError("integration_key required for acknowledging incidents")

        payload = {
            "routing_key": self.integration_key,
            "event_action": "acknowledge",
            "dedup_key": incident_id
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.events_base}/v2/enqueue",
                json=payload,
                timeout=30
            )

            if response.status_code == 202:
                return {"success": True, "message": "Incident acknowledged"}
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }

    async def test_connection(self) -> Dict[str, Any]:
        """Test PagerDuty connection"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base}/abilities",
                headers={
                    "Authorization": f"Token token={self.api_key}",
                    "Accept": "application/vnd.pagerduty+json;version=2"
                },
                timeout=30
            )

            if response.status_code == 200:
                abilities = response.json().get("abilities", [])
                return {
                    "success": True,
                    "abilities": abilities
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }
