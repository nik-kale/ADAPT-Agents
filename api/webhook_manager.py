"""
Webhook Management System
Allows users to subscribe to events and receive callbacks
"""

from typing import Dict, List, Optional, Set
from pydantic import BaseModel, HttpUrl
from datetime import datetime
import sqlite3
import json
import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)

DB_PATH = "adapt_agents.db"


class WebhookSubscription(BaseModel):
    """Webhook subscription model"""
    id: str
    url: HttpUrl
    events: List[str]  # ["analysis.started", "analysis.completed", "agent.completed", etc.]
    api_key: str
    active: bool = True
    created_at: str
    headers: Optional[Dict[str, str]] = None


class WebhookManager:
    """Manages webhook subscriptions and deliveries"""

    def __init__(self):
        self._init_db()

    def _init_db(self):
        """Initialize webhooks table"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webhooks (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                events TEXT NOT NULL,
                api_key TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                headers TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webhook_deliveries (
                id TEXT PRIMARY KEY,
                webhook_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status_code INTEGER,
                success INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                delivered_at TEXT,
                error TEXT,
                FOREIGN KEY (webhook_id) REFERENCES webhooks(id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook_id ON webhook_deliveries(webhook_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_created_at ON webhook_deliveries(created_at)")

        conn.commit()
        conn.close()

    def create_webhook(
        self,
        webhook_id: str,
        url: str,
        events: List[str],
        api_key: str,
        headers: Optional[Dict[str, str]] = None
    ):
        """Create new webhook subscription"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO webhooks (id, url, events, api_key, active, created_at, headers)
            VALUES (?, ?, ?, ?, 1, ?, ?)
        """, (
            webhook_id,
            url,
            json.dumps(events),
            api_key,
            datetime.utcnow().isoformat(),
            json.dumps(headers) if headers else None
        ))

        conn.commit()
        conn.close()

    def get_webhook(self, webhook_id: str) -> Optional[WebhookSubscription]:
        """Get webhook by ID"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, url, events, api_key, active, created_at, headers
            FROM webhooks
            WHERE id = ?
        """, (webhook_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return WebhookSubscription(
            id=row[0],
            url=row[1],
            events=json.loads(row[2]),
            api_key=row[3],
            active=bool(row[4]),
            created_at=row[5],
            headers=json.loads(row[6]) if row[6] else None
        )

    def list_webhooks(self, api_key: str) -> List[WebhookSubscription]:
        """List all webhooks for an API key"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, url, events, api_key, active, created_at, headers
            FROM webhooks
            WHERE api_key = ?
            ORDER BY created_at DESC
        """, (api_key,))

        rows = cursor.fetchall()
        conn.close()

        webhooks = []
        for row in rows:
            webhooks.append(WebhookSubscription(
                id=row[0],
                url=row[1],
                events=json.loads(row[2]),
                api_key=row[3],
                active=bool(row[4]),
                created_at=row[5],
                headers=json.loads(row[6]) if row[6] else None
            ))

        return webhooks

    def update_webhook(
        self,
        webhook_id: str,
        url: Optional[str] = None,
        events: Optional[List[str]] = None,
        active: Optional[bool] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        """Update webhook subscription"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        updates = []
        params = []

        if url is not None:
            updates.append("url = ?")
            params.append(url)

        if events is not None:
            updates.append("events = ?")
            params.append(json.dumps(events))

        if active is not None:
            updates.append("active = ?")
            params.append(1 if active else 0)

        if headers is not None:
            updates.append("headers = ?")
            params.append(json.dumps(headers))

        if updates:
            params.append(webhook_id)
            cursor.execute(f"""
                UPDATE webhooks
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)

        conn.commit()
        conn.close()

    def delete_webhook(self, webhook_id: str):
        """Delete webhook subscription"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))

        conn.commit()
        conn.close()

    async def trigger_webhooks(
        self,
        event_type: str,
        payload: Dict,
        api_key: Optional[str] = None
    ):
        """Trigger webhooks for an event"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if api_key:
            cursor.execute("""
                SELECT id, url, events, headers
                FROM webhooks
                WHERE api_key = ? AND active = 1
            """, (api_key,))
        else:
            cursor.execute("""
                SELECT id, url, events, headers
                FROM webhooks
                WHERE active = 1
            """)

        rows = cursor.fetchall()
        conn.close()

        # Filter webhooks that subscribe to this event
        webhooks_to_trigger = []
        for row in rows:
            webhook_id, url, events_json, headers_json = row
            events = json.loads(events_json)

            # Check if webhook subscribes to this event type
            if event_type in events or "*" in events:
                webhooks_to_trigger.append((
                    webhook_id,
                    url,
                    json.loads(headers_json) if headers_json else {}
                ))

        # Trigger all matching webhooks
        tasks = []
        for webhook_id, url, headers in webhooks_to_trigger:
            tasks.append(self._deliver_webhook(webhook_id, url, event_type, payload, headers))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _deliver_webhook(
        self,
        webhook_id: str,
        url: str,
        event_type: str,
        payload: Dict,
        headers: Dict[str, str]
    ):
        """Deliver webhook to endpoint"""
        import uuid

        delivery_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()

        try:
            # Prepare payload
            webhook_payload = {
                "event": event_type,
                "timestamp": created_at,
                "data": payload
            }

            # Send request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=webhook_payload,
                    headers=headers or {}
                )

                # Log delivery
                self._log_delivery(
                    delivery_id,
                    webhook_id,
                    event_type,
                    webhook_payload,
                    response.status_code,
                    True if 200 <= response.status_code < 300 else False,
                    created_at,
                    None
                )

                logger.info(f"Webhook delivered: {webhook_id} -> {url} (status: {response.status_code})")

        except Exception as e:
            # Log failed delivery
            self._log_delivery(
                delivery_id,
                webhook_id,
                event_type,
                payload,
                None,
                False,
                created_at,
                str(e)
            )

            logger.error(f"Webhook delivery failed: {webhook_id} -> {url}: {e}")

    def _log_delivery(
        self,
        delivery_id: str,
        webhook_id: str,
        event_type: str,
        payload: Dict,
        status_code: Optional[int],
        success: bool,
        created_at: str,
        error: Optional[str]
    ):
        """Log webhook delivery attempt"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO webhook_deliveries (
                id, webhook_id, event_type, payload, status_code, success, created_at, delivered_at, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            delivery_id,
            webhook_id,
            event_type,
            json.dumps(payload),
            status_code,
            1 if success else 0,
            created_at,
            datetime.utcnow().isoformat(),
            error
        ))

        conn.commit()
        conn.close()

    def get_webhook_deliveries(
        self,
        webhook_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get delivery history for a webhook"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, event_type, status_code, success, created_at, delivered_at, error
            FROM webhook_deliveries
            WHERE webhook_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (webhook_id, limit))

        rows = cursor.fetchall()
        conn.close()

        deliveries = []
        for row in rows:
            deliveries.append({
                "id": row[0],
                "event_type": row[1],
                "status_code": row[2],
                "success": bool(row[3]),
                "created_at": row[4],
                "delivered_at": row[5],
                "error": row[6]
            })

        return deliveries


# Global webhook manager
webhook_manager = WebhookManager()
