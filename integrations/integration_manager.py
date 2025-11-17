"""
Integration Manager
Centralized management of all enterprise integrations
"""

from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime
import sqlite3
import json

from integrations.slack import SlackIntegration
from integrations.jira import JiraIntegration
from integrations.pagerduty import PagerDutyIntegration


DB_PATH = "adapt_agents.db"


class IntegrationManager:
    """
    Manages all enterprise integrations

    Features:
    - Unified interface for all integrations
    - Configuration management
    - Automatic notification on incidents
    - Integration health monitoring
    - Persistent configuration storage
    """

    def __init__(self):
        """Initialize integration manager"""
        self._slack_instances: Dict[str, SlackIntegration] = {}
        self._jira_instances: Dict[str, JiraIntegration] = {}
        self._pagerduty_instances: Dict[str, PagerDutyIntegration] = {}

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize integrations database table"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS integrations (
                id TEXT PRIMARY KEY,
                api_key TEXT NOT NULL,
                integration_type TEXT NOT NULL,
                config TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                last_used TEXT
            )
        """)

        conn.commit()
        conn.close()

    def register_slack(
        self,
        integration_id: str,
        api_key: str,
        webhook_url: Optional[str] = None,
        bot_token: Optional[str] = None
    ) -> str:
        """
        Register Slack integration

        Args:
            integration_id: Unique identifier
            api_key: User API key (for access control)
            webhook_url: Slack webhook URL
            bot_token: Slack bot token

        Returns:
            Integration ID
        """
        slack = SlackIntegration(webhook_url=webhook_url, bot_token=bot_token)
        self._slack_instances[integration_id] = slack

        # Store in database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        config = {"webhook_url": webhook_url, "has_bot_token": bool(bot_token)}

        cursor.execute("""
            INSERT OR REPLACE INTO integrations (id, api_key, integration_type, config, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (integration_id, api_key, "slack", json.dumps(config), datetime.utcnow().isoformat()))

        conn.commit()
        conn.close()

        return integration_id

    def register_jira(
        self,
        integration_id: str,
        api_key: str,
        jira_url: str,
        username: str,
        jira_api_token: str,
        project_key: str
    ) -> str:
        """
        Register JIRA integration

        Args:
            integration_id: Unique identifier
            api_key: User API key
            jira_url: JIRA instance URL
            username: JIRA username
            jira_api_token: JIRA API token
            project_key: Project key

        Returns:
            Integration ID
        """
        jira = JiraIntegration(
            jira_url=jira_url,
            username=username,
            api_token=jira_api_token,
            project_key=project_key
        )
        self._jira_instances[integration_id] = jira

        # Store in database (don't store sensitive tokens in plain text in production!)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        config = {
            "jira_url": jira_url,
            "username": username,
            "project_key": project_key
        }

        cursor.execute("""
            INSERT OR REPLACE INTO integrations (id, api_key, integration_type, config, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (integration_id, api_key, "jira", json.dumps(config), datetime.utcnow().isoformat()))

        conn.commit()
        conn.close()

        return integration_id

    def register_pagerduty(
        self,
        integration_id: str,
        api_key: str,
        pd_api_key: str,
        integration_key: Optional[str] = None,
        from_email: Optional[str] = None
    ) -> str:
        """
        Register PagerDuty integration

        Args:
            integration_id: Unique identifier
            api_key: User API key
            pd_api_key: PagerDuty API key
            integration_key: Events API integration key
            from_email: User email

        Returns:
            Integration ID
        """
        pagerduty = PagerDutyIntegration(
            api_key=pd_api_key,
            integration_key=integration_key,
            from_email=from_email
        )
        self._pagerduty_instances[integration_id] = pagerduty

        # Store in database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        config = {
            "has_integration_key": bool(integration_key),
            "from_email": from_email
        }

        cursor.execute("""
            INSERT OR REPLACE INTO integrations (id, api_key, integration_type, config, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (integration_id, api_key, "pagerduty", json.dumps(config), datetime.utcnow().isoformat()))

        conn.commit()
        conn.close()

        return integration_id

    async def notify_incident(
        self,
        incident_id: str,
        incident_data: Dict[str, Any],
        api_key: str,
        slack_channel: Optional[str] = None,
        create_jira: bool = False,
        trigger_pagerduty: bool = False,
        pagerduty_service_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Notify all configured integrations about an incident

        Args:
            incident_id: Incident identifier
            incident_data: Incident details
            api_key: User API key
            slack_channel: Slack channel for notification
            create_jira: Create JIRA ticket
            trigger_pagerduty: Trigger PagerDuty incident
            pagerduty_service_id: PagerDuty service ID

        Returns:
            Results from all integrations
        """
        results = {}

        # Get user integrations
        integrations = self.list_integrations(api_key)

        # Slack notifications
        slack_integrations = [i for i in integrations if i["integration_type"] == "slack"]
        if slack_integrations:
            slack_results = []
            for integration in slack_integrations:
                if integration["id"] in self._slack_instances:
                    slack = self._slack_instances[integration["id"]]
                    try:
                        result = await slack.send_incident_alert(
                            incident_id,
                            incident_data,
                            channel=slack_channel
                        )
                        slack_results.append({
                            "integration_id": integration["id"],
                            "result": result
                        })
                    except Exception as e:
                        slack_results.append({
                            "integration_id": integration["id"],
                            "error": str(e)
                        })
            results["slack"] = slack_results

        # JIRA ticket creation
        if create_jira:
            jira_integrations = [i for i in integrations if i["integration_type"] == "jira"]
            if jira_integrations:
                jira_results = []
                for integration in jira_integrations:
                    if integration["id"] in self._jira_instances:
                        jira = self._jira_instances[integration["id"]]
                        try:
                            result = await jira.create_incident_ticket(
                                incident_id,
                                incident_data
                            )
                            jira_results.append({
                                "integration_id": integration["id"],
                                "result": result
                            })
                        except Exception as e:
                            jira_results.append({
                                "integration_id": integration["id"],
                                "error": str(e)
                            })
                results["jira"] = jira_results

        # PagerDuty incident
        if trigger_pagerduty:
            pd_integrations = [i for i in integrations if i["integration_type"] == "pagerduty"]
            if pd_integrations:
                pd_results = []
                for integration in pd_integrations:
                    if integration["id"] in self._pagerduty_instances:
                        pagerduty = self._pagerduty_instances[integration["id"]]
                        try:
                            if pagerduty_service_id:
                                result = await pagerduty.create_incident(
                                    incident_id,
                                    incident_data,
                                    pagerduty_service_id
                                )
                            else:
                                result = await pagerduty.trigger_incident(
                                    incident_id,
                                    incident_data
                                )
                            pd_results.append({
                                "integration_id": integration["id"],
                                "result": result
                            })
                        except Exception as e:
                            pd_results.append({
                                "integration_id": integration["id"],
                                "error": str(e)
                            })
                results["pagerduty"] = pd_results

        # Update last_used timestamp
        self._update_last_used(api_key)

        return results

    async def notify_rca_complete(
        self,
        incident_id: str,
        rca_results: Dict[str, Any],
        api_key: str,
        slack_channel: Optional[str] = None,
        jira_issue_key: Optional[str] = None,
        pagerduty_incident_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Notify integrations about completed RCA

        Args:
            incident_id: Incident identifier
            rca_results: Complete RCA results
            api_key: User API key
            slack_channel: Slack channel
            jira_issue_key: JIRA issue to comment on
            pagerduty_incident_id: PagerDuty incident to add note to

        Returns:
            Results from all integrations
        """
        results = {}
        integrations = self.list_integrations(api_key)

        # Slack summary
        slack_integrations = [i for i in integrations if i["integration_type"] == "slack"]
        if slack_integrations:
            slack_results = []
            for integration in slack_integrations:
                if integration["id"] in self._slack_instances:
                    slack = self._slack_instances[integration["id"]]
                    try:
                        result = await slack.send_rca_summary(
                            incident_id,
                            rca_results,
                            channel=slack_channel
                        )
                        slack_results.append({
                            "integration_id": integration["id"],
                            "result": result
                        })
                    except Exception as e:
                        slack_results.append({
                            "integration_id": integration["id"],
                            "error": str(e)
                        })
            results["slack"] = slack_results

        # JIRA comment
        if jira_issue_key:
            jira_integrations = [i for i in integrations if i["integration_type"] == "jira"]
            if jira_integrations:
                jira_results = []
                for integration in jira_integrations:
                    if integration["id"] in self._jira_instances:
                        jira = self._jira_instances[integration["id"]]
                        try:
                            result = await jira.add_rca_comment(
                                jira_issue_key,
                                rca_results
                            )
                            jira_results.append({
                                "integration_id": integration["id"],
                                "result": result
                            })
                        except Exception as e:
                            jira_results.append({
                                "integration_id": integration["id"],
                                "error": str(e)
                            })
                results["jira"] = jira_results

        # PagerDuty note
        if pagerduty_incident_id:
            pd_integrations = [i for i in integrations if i["integration_type"] == "pagerduty"]
            if pd_integrations:
                pd_results = []
                for integration in pd_integrations:
                    if integration["id"] in self._pagerduty_instances:
                        pagerduty = self._pagerduty_instances[integration["id"]]
                        try:
                            result = await pagerduty.add_rca_note(
                                pagerduty_incident_id,
                                rca_results
                            )
                            pd_results.append({
                                "integration_id": integration["id"],
                                "result": result
                            })
                        except Exception as e:
                            pd_results.append({
                                "integration_id": integration["id"],
                                "error": str(e)
                            })
                results["pagerduty"] = pd_results

        return results

    def list_integrations(self, api_key: str) -> List[Dict[str, Any]]:
        """List all integrations for an API key"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, integration_type, config, enabled, created_at, last_used
            FROM integrations
            WHERE api_key = ? AND enabled = 1
        """, (api_key,))

        rows = cursor.fetchall()
        conn.close()

        integrations = []
        for row in rows:
            integrations.append({
                "id": row[0],
                "integration_type": row[1],
                "config": json.loads(row[2]),
                "enabled": bool(row[3]),
                "created_at": row[4],
                "last_used": row[5]
            })

        return integrations

    def delete_integration(self, integration_id: str, api_key: str) -> bool:
        """Delete integration"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM integrations
            WHERE id = ? AND api_key = ?
        """, (integration_id, api_key))

        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        # Remove from memory
        if integration_id in self._slack_instances:
            del self._slack_instances[integration_id]
        if integration_id in self._jira_instances:
            del self._jira_instances[integration_id]
        if integration_id in self._pagerduty_instances:
            del self._pagerduty_instances[integration_id]

        return deleted

    def _update_last_used(self, api_key: str):
        """Update last_used timestamp for integrations"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE integrations
            SET last_used = ?
            WHERE api_key = ?
        """, (datetime.utcnow().isoformat(), api_key))

        conn.commit()
        conn.close()

    async def test_all_integrations(self, api_key: str) -> Dict[str, Any]:
        """Test all configured integrations"""
        integrations = self.list_integrations(api_key)
        results = {}

        for integration in integrations:
            integration_id = integration["id"]
            integration_type = integration["integration_type"]

            try:
                if integration_type == "slack" and integration_id in self._slack_instances:
                    result = await self._slack_instances[integration_id].test_connection()
                    results[integration_id] = {"type": "slack", "test": result}

                elif integration_type == "jira" and integration_id in self._jira_instances:
                    result = await self._jira_instances[integration_id].test_connection()
                    results[integration_id] = {"type": "jira", "test": result}

                elif integration_type == "pagerduty" and integration_id in self._pagerduty_instances:
                    result = await self._pagerduty_instances[integration_id].test_connection()
                    results[integration_id] = {"type": "pagerduty", "test": result}

            except Exception as e:
                results[integration_id] = {"type": integration_type, "error": str(e)}

        return results


# Global integration manager instance
integration_manager = IntegrationManager()
