"""
Integrations Management API Routes
Provides endpoints for configuring and managing enterprise integrations
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Optional, List, Any
import uuid

from integrations.integration_manager import integration_manager


router = APIRouter()


# Pydantic models
class SlackIntegrationCreate(BaseModel):
    """Create Slack integration"""
    webhook_url: Optional[str] = None
    bot_token: Optional[str] = None


class JiraIntegrationCreate(BaseModel):
    """Create JIRA integration"""
    jira_url: str
    username: str
    api_token: str
    project_key: str


class PagerDutyIntegrationCreate(BaseModel):
    """Create PagerDuty integration"""
    api_key: str
    integration_key: Optional[str] = None
    from_email: Optional[str] = None


class NotifyIncidentRequest(BaseModel):
    """Request to notify integrations about incident"""
    incident_id: str
    incident_data: Dict[str, Any]
    slack_channel: Optional[str] = None
    create_jira: bool = False
    trigger_pagerduty: bool = False
    pagerduty_service_id: Optional[str] = None


class NotifyRCARequest(BaseModel):
    """Request to notify integrations about RCA completion"""
    incident_id: str
    rca_results: Dict[str, Any]
    slack_channel: Optional[str] = None
    jira_issue_key: Optional[str] = None
    pagerduty_incident_id: Optional[str] = None


@router.post("/integrations/slack", tags=["integrations"])
async def create_slack_integration(
    integration: SlackIntegrationCreate,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Configure Slack integration

    Supports two modes:
    - Incoming webhook (simpler, limited features)
    - Bot token (full API access)

    Example:
    ```json
    {
        "webhook_url": "https://hooks.slack.com/services/..."
    }
    ```
    """
    if not integration.webhook_url and not integration.bot_token:
        raise HTTPException(
            status_code=400,
            detail="Either webhook_url or bot_token must be provided"
        )

    integration_id = str(uuid.uuid4())

    try:
        integration_manager.register_slack(
            integration_id=integration_id,
            api_key=api_key,
            webhook_url=integration.webhook_url,
            bot_token=integration.bot_token
        )

        return {
            "integration_id": integration_id,
            "integration_type": "slack",
            "message": "Slack integration created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create integration: {str(e)}")


@router.post("/integrations/jira", tags=["integrations"])
async def create_jira_integration(
    integration: JiraIntegrationCreate,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Configure JIRA integration

    Creates JIRA tickets automatically for incidents and remediation tasks.

    Example:
    ```json
    {
        "jira_url": "https://your-domain.atlassian.net",
        "username": "your-email@example.com",
        "api_token": "your-api-token",
        "project_key": "INCIDENT"
    }
    ```
    """
    integration_id = str(uuid.uuid4())

    try:
        integration_manager.register_jira(
            integration_id=integration_id,
            api_key=api_key,
            jira_url=integration.jira_url,
            username=integration.username,
            jira_api_token=integration.api_token,
            project_key=integration.project_key
        )

        return {
            "integration_id": integration_id,
            "integration_type": "jira",
            "message": "JIRA integration created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create integration: {str(e)}")


@router.post("/integrations/pagerduty", tags=["integrations"])
async def create_pagerduty_integration(
    integration: PagerDutyIntegrationCreate,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Configure PagerDuty integration

    Supports both Events API (for triggering) and REST API (for management).

    Example:
    ```json
    {
        "api_key": "your-pagerduty-api-key",
        "integration_key": "your-events-integration-key",
        "from_email": "your-email@example.com"
    }
    ```
    """
    integration_id = str(uuid.uuid4())

    try:
        integration_manager.register_pagerduty(
            integration_id=integration_id,
            api_key=api_key,
            pd_api_key=integration.api_key,
            integration_key=integration.integration_key,
            from_email=integration.from_email
        )

        return {
            "integration_id": integration_id,
            "integration_type": "pagerduty",
            "message": "PagerDuty integration created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create integration: {str(e)}")


@router.get("/integrations", tags=["integrations"])
async def list_integrations(
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    List all configured integrations

    Returns all active integrations for the authenticated user.
    """
    try:
        integrations = integration_manager.list_integrations(api_key)

        return {
            "integrations": integrations,
            "total": len(integrations)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list integrations: {str(e)}")


@router.delete("/integrations/{integration_id}", tags=["integrations"])
async def delete_integration(
    integration_id: str,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Delete integration

    Permanently removes the integration configuration.
    """
    try:
        success = integration_manager.delete_integration(integration_id, api_key)

        if not success:
            raise HTTPException(status_code=404, detail="Integration not found")

        return {
            "integration_id": integration_id,
            "message": "Integration deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete integration: {str(e)}")


@router.post("/integrations/notify/incident", tags=["integrations"])
async def notify_incident(
    request: NotifyIncidentRequest,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Notify all configured integrations about an incident

    Sends notifications to:
    - Slack (if configured)
    - JIRA (creates ticket if requested)
    - PagerDuty (triggers incident if requested)

    Example:
    ```json
    {
        "incident_id": "inc-12345",
        "incident_data": {
            "incident_time": "2025-01-15T10:00:00Z",
            "severity": "critical",
            "affected_services": ["api-service"]
        },
        "slack_channel": "#incidents",
        "create_jira": true,
        "trigger_pagerduty": true
    }
    ```
    """
    try:
        results = await integration_manager.notify_incident(
            incident_id=request.incident_id,
            incident_data=request.incident_data,
            api_key=api_key,
            slack_channel=request.slack_channel,
            create_jira=request.create_jira,
            trigger_pagerduty=request.trigger_pagerduty,
            pagerduty_service_id=request.pagerduty_service_id
        )

        return {
            "incident_id": request.incident_id,
            "notifications_sent": results,
            "message": "Notifications sent successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send notifications: {str(e)}")


@router.post("/integrations/notify/rca-complete", tags=["integrations"])
async def notify_rca_complete(
    request: NotifyRCARequest,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Notify integrations about RCA completion

    Sends RCA summary to:
    - Slack (formatted summary)
    - JIRA (comment on issue)
    - PagerDuty (note on incident)

    Example:
    ```json
    {
        "incident_id": "inc-12345",
        "rca_results": {...},
        "slack_channel": "#incidents",
        "jira_issue_key": "INCIDENT-123",
        "pagerduty_incident_id": "PD12345"
    }
    ```
    """
    try:
        results = await integration_manager.notify_rca_complete(
            incident_id=request.incident_id,
            rca_results=request.rca_results,
            api_key=api_key,
            slack_channel=request.slack_channel,
            jira_issue_key=request.jira_issue_key,
            pagerduty_incident_id=request.pagerduty_incident_id
        )

        return {
            "incident_id": request.incident_id,
            "notifications_sent": results,
            "message": "RCA notifications sent successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send RCA notifications: {str(e)}")


@router.post("/integrations/test", tags=["integrations"])
async def test_integrations(
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Test all configured integrations

    Verifies connectivity and authentication for each integration.
    """
    try:
        results = await integration_manager.test_all_integrations(api_key)

        return {
            "test_results": results,
            "total_tested": len(results)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test integrations: {str(e)}")
