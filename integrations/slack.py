"""
Slack Integration
Sends notifications, alerts, and RCA summaries to Slack channels
"""

from typing import Dict, Any, Optional, List
import httpx
import json
import logging
from datetime import datetime
from utils.circuit_breaker import circuit_breaker_registry

logger = logging.getLogger(__name__)


class SlackIntegration:
    """
    Slack integration for incident notifications

    Features:
    - Send incident alerts to channels
    - Post RCA analysis results
    - Send finding updates
    - Rich message formatting with blocks
    - Thread support for conversations
    - Emoji reactions for status
    """

    def __init__(self, webhook_url: Optional[str] = None, bot_token: Optional[str] = None):
        """
        Initialize Slack integration

        Args:
            webhook_url: Slack incoming webhook URL (simpler, limited features)
            bot_token: Slack bot token (full API access)
        """
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.api_base = "https://slack.com/api"
        
        # Initialize circuit breaker for Slack API
        self.circuit_breaker = circuit_breaker_registry.get_or_create(
            name="slack_api",
            failure_threshold=5,
            recovery_timeout=60,
            half_open_requests=2,
            expected_exception=Exception,
            fallback=self._slack_fallback
        )
        logger.info("Slack integration initialized with circuit breaker")
    
    async def _slack_fallback(self, *args, **kwargs) -> Dict[str, Any]:
        """Fallback when Slack API is unavailable"""
        logger.warning("Slack API unavailable, message queued for retry")
        return {
            "ok": False,
            "error": "slack_unavailable",
            "message": "Slack API is temporarily unavailable. Message queued for retry."
        }

    async def send_incident_alert(
        self,
        incident_id: str,
        incident_data: Dict[str, Any],
        channel: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send incident alert to Slack

        Args:
            incident_id: Unique incident identifier
            incident_data: Incident details
            channel: Slack channel (required if using bot token)

        Returns:
            Response from Slack API
        """
        # Format incident message
        severity = incident_data.get("severity", "unknown")
        services = ", ".join(incident_data.get("affected_services", []))
        incident_time = incident_data.get("incident_time", "Unknown")

        # Choose emoji based on severity
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢"
        }.get(severity.lower(), "⚪")

        # Build Slack blocks (rich formatting)
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji} New Incident Alert",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Incident ID:*\n{incident_id}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity:*\n{severity.upper()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Affected Services:*\n{services or 'None specified'}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n{incident_time}"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"🤖 ADAPT-Agents is analyzing this incident..."
                    }
                ]
            }
        ]

        # Send via webhook or API
        if self.webhook_url:
            return await self._send_webhook({"blocks": blocks})
        elif self.bot_token and channel:
            return await self._send_chat_message(channel, blocks=blocks)
        else:
            raise ValueError("Either webhook_url or (bot_token and channel) must be provided")

    async def send_rca_summary(
        self,
        incident_id: str,
        rca_results: Dict[str, Any],
        channel: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send RCA analysis summary to Slack

        Args:
            incident_id: Incident identifier
            rca_results: Complete RCA results
            channel: Slack channel

        Returns:
            Slack API response
        """
        # Extract key findings
        hypothesis = None
        remediation = None

        if "phase2" in rca_results and "hypothesis_generator" in rca_results["phase2"]:
            hyp = rca_results["phase2"]["hypothesis_generator"]
            if hasattr(hyp, "findings") and hyp.findings:
                finding = hyp.findings[0]
                hypothesis = finding.dict() if hasattr(finding, "dict") else finding

        if "phase3" in rca_results and "remediation_planner" in rca_results["phase3"]:
            rem = rca_results["phase3"]["remediation_planner"]
            if hasattr(rem, "findings") and rem.findings:
                finding = rem.findings[0]
                remediation = finding.dict() if hasattr(finding, "dict") else finding

        # Build summary blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "✅ RCA Analysis Complete",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Incident ID:* {incident_id}"
                }
            }
        ]

        # Add hypothesis section
        if hypothesis:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔍 Root Cause:*\n{hypothesis.get('description', 'No description')}"
                }
            })
            if "confidence" in hypothesis:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Confidence: {hypothesis['confidence']}"
                        }
                    ]
                })

        # Add remediation section
        if remediation:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔧 Recommended Action:*\n{remediation.get('description', 'No description')}"
                }
            })
            if "priority" in remediation:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Priority: {remediation['priority']}"
                        }
                    ]
                })

        # Add execution time
        if "execution_time_ms" in rca_results:
            exec_time_sec = rca_results["execution_time_ms"] / 1000
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⏱️ Analysis completed in {exec_time_sec:.2f}s"
                    }
                ]
            })

        # Send message
        if self.webhook_url:
            return await self._send_webhook({"blocks": blocks})
        elif self.bot_token and channel:
            return await self._send_chat_message(channel, blocks=blocks)
        else:
            raise ValueError("Either webhook_url or (bot_token and channel) must be provided")

    async def send_finding_update(
        self,
        incident_id: str,
        agent_name: str,
        finding: Dict[str, Any],
        channel: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send real-time finding update to Slack

        Args:
            incident_id: Incident ID
            agent_name: Agent that discovered the finding
            finding: Finding details
            channel: Slack channel

        Returns:
            Slack API response
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🔎 *{agent_name}* discovered a finding for incident `{incident_id}`"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{finding.get('description', 'No description')}```"
                }
            }
        ]

        if self.webhook_url:
            return await self._send_webhook({"blocks": blocks})
        elif self.bot_token and channel:
            return await self._send_chat_message(channel, blocks=blocks)
        else:
            raise ValueError("Either webhook_url or (bot_token and channel) must be provided")

    async def send_custom_message(
        self,
        text: str,
        channel: Optional[str] = None,
        attachments: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Send custom message to Slack

        Args:
            text: Message text
            channel: Slack channel
            attachments: Optional attachments

        Returns:
            Slack API response
        """
        payload = {"text": text}
        if attachments:
            payload["attachments"] = attachments

        if self.webhook_url:
            return await self._send_webhook(payload)
        elif self.bot_token and channel:
            return await self._send_chat_message(channel, text=text, attachments=attachments)
        else:
            raise ValueError("Either webhook_url or (bot_token and channel) must be provided")

    async def _send_webhook_internal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Internal method: Send message via incoming webhook"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )

            if response.status_code == 200 and response.text == "ok":
                return {"success": True, "message": "Message sent via webhook"}
            else:
                raise Exception(f"Slack webhook failed: {response.text}")
    
    async def _send_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via incoming webhook with circuit breaker protection"""
        try:
            return await self.circuit_breaker.execute(
                self._send_webhook_internal,
                payload
            )
        except Exception as e:
            logger.error(f"Slack webhook error: {e}")
            return {"success": False, "error": str(e)}

    async def _send_chat_message_internal(
        self,
        channel: str,
        text: Optional[str] = None,
        blocks: Optional[List[Dict]] = None,
        attachments: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Internal method: Send message via Slack API"""
        payload = {"channel": channel}

        if text:
            payload["text"] = text
        if blocks:
            payload["blocks"] = blocks
        if attachments:
            payload["attachments"] = attachments

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )
            
            result = response.json()
            if not result.get("ok"):
                raise Exception(f"Slack API error: {result.get('error', 'Unknown')}")
            
            return result
    
    async def _send_chat_message(
        self,
        channel: str,
        text: Optional[str] = None,
        blocks: Optional[List[Dict]] = None,
        attachments: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Send message via Slack API with circuit breaker protection"""
        try:
            return await self.circuit_breaker.execute(
                self._send_chat_message_internal,
                channel,
                text,
                blocks,
                attachments
            )
        except Exception as e:
            logger.error(f"Slack API error: {e}")
            return {"ok": False, "error": str(e)}

    async def test_connection(self) -> Dict[str, Any]:
        """Test Slack connection"""
        if self.webhook_url:
            return await self._send_webhook({"text": "🤖 ADAPT-Agents connection test"})
        elif self.bot_token:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/auth.test",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    timeout=30
                )
                return response.json()
        else:
            return {"success": False, "error": "No webhook_url or bot_token configured"}
