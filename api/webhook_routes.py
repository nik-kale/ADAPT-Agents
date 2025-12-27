"""
Webhook Management API Routes
Provides endpoints for webhook subscription management
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Optional
import uuid

from api.webhook_manager import webhook_manager
from api.auth import get_api_key

router = APIRouter()


class WebhookCreate(BaseModel):
    """Request to create webhook"""
    url: HttpUrl
    events: List[str]  # ["analysis.started", "analysis.completed", "agent.completed", "finding.discovered"]
    headers: Optional[Dict[str, str]] = None


class WebhookUpdate(BaseModel):
    """Request to update webhook"""
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = None
    active: Optional[bool] = None
    headers: Optional[Dict[str, str]] = None


@router.post("/webhooks", tags=["webhooks"])
async def create_webhook(
    webhook_data: WebhookCreate,
    api_key: str = Depends(get_api_key)
):
    """
    Create new webhook subscription

    Subscribe to events:
    - `analysis.started` - When analysis begins
    - `analysis.completed` - When analysis finishes
    - `agent.started` - When agent execution starts
    - `agent.completed` - When agent finishes
    - `finding.discovered` - When finding is discovered
    - `error.occurred` - When error occurs
    - `*` - All events

    Example:
    ```json
    {
        "url": "https://your-app.com/webhooks",
        "events": ["analysis.completed", "error.occurred"],
        "headers": {
            "Authorization": "Bearer your-token"
        }
    }
    ```
    """
    webhook_id = str(uuid.uuid4())

    webhook_manager.create_webhook(
        webhook_id=webhook_id,
        url=str(webhook_data.url),
        events=webhook_data.events,
        api_key=api_key,
        headers=webhook_data.headers
    )

    return {
        "id": webhook_id,
        "url": str(webhook_data.url),
        "events": webhook_data.events,
        "active": True,
        "message": "Webhook created successfully"
    }


@router.get("/webhooks", tags=["webhooks"])
async def list_webhooks(
    api_key: str = Depends(get_api_key)
):
    """
    List all webhooks for the authenticated API key

    Returns all webhook subscriptions with their configuration and status.
    """
    webhooks = webhook_manager.list_webhooks(api_key)

    return {
        "webhooks": [webhook.dict() for webhook in webhooks],
        "total": len(webhooks)
    }


@router.get("/webhooks/{webhook_id}", tags=["webhooks"])
async def get_webhook(
    webhook_id: str,
    api_key: str = Depends(get_api_key)
):
    """
    Get webhook details by ID

    Returns webhook configuration and recent delivery history.
    """
    webhook = webhook_manager.get_webhook(webhook_id)

    if not webhook or webhook.api_key != api_key:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Get delivery history
    deliveries = webhook_manager.get_webhook_deliveries(webhook_id, limit=20)

    return {
        "webhook": webhook.dict(),
        "recent_deliveries": deliveries
    }


@router.patch("/webhooks/{webhook_id}", tags=["webhooks"])
async def update_webhook(
    webhook_id: str,
    updates: WebhookUpdate,
    api_key: str = Depends(get_api_key)
):
    """
    Update webhook configuration

    Update URL, events, active status, or headers.
    """
    webhook = webhook_manager.get_webhook(webhook_id)

    if not webhook or webhook.api_key != api_key:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook_manager.update_webhook(
        webhook_id=webhook_id,
        url=str(updates.url) if updates.url else None,
        events=updates.events,
        active=updates.active,
        headers=updates.headers
    )

    return {
        "id": webhook_id,
        "message": "Webhook updated successfully"
    }


@router.delete("/webhooks/{webhook_id}", tags=["webhooks"])
async def delete_webhook(
    webhook_id: str,
    api_key: str = Depends(get_api_key)
):
    """
    Delete webhook subscription

    Permanently removes the webhook. Cannot be undone.
    """
    webhook = webhook_manager.get_webhook(webhook_id)

    if not webhook or webhook.api_key != api_key:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook_manager.delete_webhook(webhook_id)

    return {
        "id": webhook_id,
        "message": "Webhook deleted successfully"
    }


@router.get("/webhooks/{webhook_id}/deliveries", tags=["webhooks"])
async def get_webhook_deliveries(
    webhook_id: str,
    limit: int = 50,
    api_key: str = Depends(get_api_key)
):
    """
    Get delivery history for a webhook

    Shows recent webhook deliveries including status, timestamps, and errors.
    """
    webhook = webhook_manager.get_webhook(webhook_id)

    if not webhook or webhook.api_key != api_key:
        raise HTTPException(status_code=404, detail="Webhook not found")

    deliveries = webhook_manager.get_webhook_deliveries(webhook_id, limit)

    success_count = sum(1 for d in deliveries if d["success"])
    failure_count = len(deliveries) - success_count

    return {
        "webhook_id": webhook_id,
        "deliveries": deliveries,
        "total": len(deliveries),
        "success_count": success_count,
        "failure_count": failure_count
    }


@router.post("/webhooks/{webhook_id}/test", tags=["webhooks"])
async def test_webhook(
    webhook_id: str,
    api_key: str = Depends(get_api_key)
):
    """
    Test webhook by sending a test event

    Sends a test event to verify the webhook is configured correctly.
    """
    webhook = webhook_manager.get_webhook(webhook_id)

    if not webhook or webhook.api_key != api_key:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Send test event
    await webhook_manager.trigger_webhooks(
        event_type="webhook.test",
        payload={
            "webhook_id": webhook_id,
            "message": "This is a test webhook delivery"
        },
        api_key=api_key
    )

    return {
        "message": "Test webhook sent",
        "webhook_id": webhook_id
    }
