"""
JIRA Integration
Creates tickets, updates status, and manages remediation tasks in JIRA
"""

from typing import Dict, Any, Optional, List
import httpx
import json
import base64
from datetime import datetime


class JiraIntegration:
    """
    JIRA integration for incident management

    Features:
    - Create incidents as JIRA issues
    - Create remediation tasks
    - Update issue status
    - Add comments with findings
    - Link related issues
    - Custom field support
    """

    def __init__(
        self,
        jira_url: str,
        username: str,
        api_token: str,
        project_key: str
    ):
        """
        Initialize JIRA integration

        Args:
            jira_url: JIRA instance URL (e.g., https://your-domain.atlassian.net)
            username: JIRA username/email
            api_token: JIRA API token
            project_key: Default project key (e.g., 'INCIDENT')
        """
        self.jira_url = jira_url.rstrip('/')
        self.username = username
        self.api_token = api_token
        self.project_key = project_key

        # Build auth header
        auth_string = f"{username}:{api_token}"
        auth_bytes = auth_string.encode('utf-8')
        auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
        self.auth_header = f"Basic {auth_b64}"

    async def create_incident_ticket(
        self,
        incident_id: str,
        incident_data: Dict[str, Any],
        issue_type: str = "Bug"
    ) -> Dict[str, Any]:
        """
        Create JIRA ticket for incident

        Args:
            incident_id: Incident identifier
            incident_data: Incident details
            issue_type: JIRA issue type (Bug, Incident, Task, etc.)

        Returns:
            Created issue details
        """
        # Build summary
        services = ", ".join(incident_data.get("affected_services", []))
        summary = f"[{incident_id}] Incident in {services}" if services else f"[{incident_id}] System Incident"

        # Build description
        description_parts = [
            f"*Incident ID:* {incident_id}",
            f"*Time:* {incident_data.get('incident_time', 'Unknown')}",
            f"*Severity:* {incident_data.get('severity', 'Unknown')}",
            f"*Affected Services:* {services or 'Not specified'}",
            "",
            "*Details:*"
        ]

        # Add log summary if available
        if "logs" in incident_data and incident_data["logs"]:
            error_logs = [log for log in incident_data["logs"] if log.get("level") == "ERROR"][:5]
            if error_logs:
                description_parts.append("\n*Recent Error Logs:*")
                for log in error_logs:
                    description_parts.append(f"- {log.get('message', '')}")

        # Add metrics summary
        if "metrics" in incident_data and incident_data["metrics"]:
            description_parts.append("\n*Key Metrics:*")
            for metric in incident_data["metrics"][:5]:
                metric_name = metric.get("name", "Unknown")
                description_parts.append(f"- {metric_name}")

        description = "\n".join(description_parts)

        # Priority mapping (JIRA uses: Highest, High, Medium, Low, Lowest)
        priority_map = {
            "critical": "Highest",
            "high": "High",
            "medium": "Medium",
            "low": "Low"
        }
        priority = priority_map.get(incident_data.get("severity", "medium").lower(), "Medium")

        # Create issue payload
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
                "priority": {"name": priority}
            }
        }

        # Create issue
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.jira_url}/rest/api/3/issue",
                headers={
                    "Authorization": self.auth_header,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    "success": True,
                    "issue_key": result.get("key"),
                    "issue_id": result.get("id"),
                    "url": f"{self.jira_url}/browse/{result.get('key')}"
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }

    async def add_rca_comment(
        self,
        issue_key: str,
        rca_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add RCA results as comment to JIRA issue

        Args:
            issue_key: JIRA issue key (e.g., 'INCIDENT-123')
            rca_results: Complete RCA results

        Returns:
            Comment creation response
        """
        # Extract findings
        comment_parts = ["*Root Cause Analysis Complete*\n"]

        # Add hypothesis
        if "phase2" in rca_results and "hypothesis_generator" in rca_results["phase2"]:
            hyp = rca_results["phase2"]["hypothesis_generator"]
            if hasattr(hyp, "findings") and hyp.findings:
                comment_parts.append("*Root Cause:*")
                for idx, finding in enumerate(hyp.findings[:3], 1):
                    finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                    comment_parts.append(f"{idx}. {finding_dict.get('description', 'N/A')}")
                    if "confidence" in finding_dict:
                        comment_parts.append(f"   - Confidence: {finding_dict['confidence']}")
                comment_parts.append("")

        # Add remediation
        if "phase3" in rca_results and "remediation_planner" in rca_results["phase3"]:
            rem = rca_results["phase3"]["remediation_planner"]
            if hasattr(rem, "findings") and rem.findings:
                comment_parts.append("*Recommended Actions:*")
                for idx, finding in enumerate(rem.findings[:3], 1):
                    finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                    comment_parts.append(f"{idx}. {finding_dict.get('description', 'N/A')}")
                    if "priority" in finding_dict:
                        comment_parts.append(f"   - Priority: {finding_dict['priority']}")
                    if "estimated_time" in finding_dict:
                        comment_parts.append(f"   - Estimated Time: {finding_dict['estimated_time']}")
                comment_parts.append("")

        # Add execution time
        if "execution_time_ms" in rca_results:
            exec_time_sec = rca_results["execution_time_ms"] / 1000
            comment_parts.append(f"_Analysis completed in {exec_time_sec:.2f}s_")

        comment_body = "\n".join(comment_parts)

        # Post comment
        payload = {
            "body": comment_body
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.jira_url}/rest/api/3/issue/{issue_key}/comment",
                headers={
                    "Authorization": self.auth_header,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                return {"success": True, "comment": response.json()}
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }

    async def create_remediation_tasks(
        self,
        parent_issue_key: str,
        remediation_findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create subtasks for remediation actions

        Args:
            parent_issue_key: Parent issue key
            remediation_findings: List of remediation findings

        Returns:
            List of created task details
        """
        created_tasks = []

        for idx, finding in enumerate(remediation_findings[:5], 1):  # Limit to 5 tasks
            summary = f"Remediation {idx}: {finding.get('description', 'Unknown')[:80]}"

            # Build description
            description = finding.get('description', '')
            if "details" in finding:
                description += f"\n\nDetails:\n{finding['details']}"

            # Priority mapping
            priority_map = {
                "critical": "Highest",
                "high": "High",
                "medium": "Medium",
                "low": "Low"
            }
            priority = priority_map.get(finding.get("priority", "medium").lower(), "Medium")

            payload = {
                "fields": {
                    "project": {"key": self.project_key},
                    "summary": summary,
                    "description": description,
                    "issuetype": {"name": "Sub-task"},
                    "parent": {"key": parent_issue_key},
                    "priority": {"name": priority}
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.jira_url}/rest/api/3/issue",
                    headers={
                        "Authorization": self.auth_header,
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=30
                )

                if response.status_code in [200, 201]:
                    result = response.json()
                    created_tasks.append({
                        "success": True,
                        "issue_key": result.get("key"),
                        "url": f"{self.jira_url}/browse/{result.get('key')}"
                    })
                else:
                    created_tasks.append({
                        "success": False,
                        "error": response.text
                    })

        return created_tasks

    async def update_issue_status(
        self,
        issue_key: str,
        transition_name: str
    ) -> Dict[str, Any]:
        """
        Update issue status (transition)

        Args:
            issue_key: JIRA issue key
            transition_name: Transition name (e.g., 'In Progress', 'Resolved', 'Closed')

        Returns:
            Transition response
        """
        # Get available transitions
        async with httpx.AsyncClient() as client:
            # First, get available transitions
            transitions_response = await client.get(
                f"{self.jira_url}/rest/api/3/issue/{issue_key}/transitions",
                headers={"Authorization": self.auth_header},
                timeout=30
            )

            if transitions_response.status_code != 200:
                return {
                    "success": False,
                    "error": "Failed to get transitions",
                    "status_code": transitions_response.status_code
                }

            transitions = transitions_response.json().get("transitions", [])

            # Find matching transition
            transition_id = None
            for trans in transitions:
                if trans.get("name", "").lower() == transition_name.lower():
                    transition_id = trans.get("id")
                    break

            if not transition_id:
                return {
                    "success": False,
                    "error": f"Transition '{transition_name}' not found",
                    "available_transitions": [t.get("name") for t in transitions]
                }

            # Execute transition
            payload = {"transition": {"id": transition_id}}

            response = await client.post(
                f"{self.jira_url}/rest/api/3/issue/{issue_key}/transitions",
                headers={
                    "Authorization": self.auth_header,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )

            if response.status_code == 204:
                return {"success": True, "transition": transition_name}
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }

    async def test_connection(self) -> Dict[str, Any]:
        """Test JIRA connection"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.jira_url}/rest/api/3/myself",
                headers={"Authorization": self.auth_header},
                timeout=30
            )

            if response.status_code == 200:
                user = response.json()
                return {
                    "success": True,
                    "user": user.get("displayName"),
                    "email": user.get("emailAddress")
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }
