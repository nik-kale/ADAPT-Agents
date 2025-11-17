"""
WebSocket Routes for Real-Time Streaming
Provides WebSocket endpoints for live agent execution updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import json
import logging

from api.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/analysis/{analysis_id}")
async def websocket_analysis_endpoint(
    websocket: WebSocket,
    analysis_id: str
):
    """
    WebSocket endpoint for specific analysis real-time updates

    Streams real-time status updates for a specific analysis:
    - Agent execution status
    - Phase progress
    - Findings as they're discovered
    - Completion notifications
    - Errors

    Usage:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/ws/analysis/{analysis_id}');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Update:', data);
    };
    ```
    """
    await manager.connect(websocket, analysis_id)

    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            json.dumps({
                "type": "connected",
                "analysis_id": analysis_id,
                "message": f"Connected to analysis {analysis_id}"
            }),
            websocket
        )

        # Keep connection alive and handle incoming messages
        while True:
            # Wait for client messages (ping/pong, commands, etc.)
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle client commands
                if message.get("type") == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong"}),
                        websocket
                    )
                elif message.get("type") == "subscribe":
                    # Client can subscribe to specific event types
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "subscribed",
                            "subscription": message.get("events", [])
                        }),
                        websocket
                    )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                break

    except WebSocketDisconnect:
        manager.disconnect(websocket, analysis_id)
        logger.info(f"Client disconnected from analysis {analysis_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, analysis_id)


@router.websocket("/ws/broadcast")
async def websocket_broadcast_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for broadcast updates

    Streams all analysis updates across the system:
    - New analyses started
    - Completions
    - System-wide statistics

    Usage:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/ws/broadcast');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('System update:', data);
    };
    ```
    """
    await manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            json.dumps({
                "type": "connected",
                "message": "Connected to broadcast channel"
            }),
            websocket
        )

        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong"}),
                        websocket
                    )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in broadcast WebSocket: {e}")
                break

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected from broadcast")
    except Exception as e:
        logger.error(f"Broadcast WebSocket error: {e}")
        manager.disconnect(websocket)


@router.websocket("/ws/agent/{agent_name}")
async def websocket_agent_endpoint(
    websocket: WebSocket,
    agent_name: str,
    analysis_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for specific agent updates

    Streams updates for a specific agent across all analyses or for a specific analysis:
    - Agent starts
    - Progress updates
    - Findings
    - Completions

    Usage:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/ws/agent/LogAnalyzerAgent?analysis_id=xxx');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Agent update:', data);
    };
    ```
    """
    connection_id = f"{agent_name}:{analysis_id}" if analysis_id else agent_name
    await manager.connect(websocket, connection_id)

    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            json.dumps({
                "type": "connected",
                "agent_name": agent_name,
                "analysis_id": analysis_id,
                "message": f"Connected to {agent_name} updates"
            }),
            websocket
        )

        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong"}),
                        websocket
                    )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in agent WebSocket: {e}")
                break

    except WebSocketDisconnect:
        manager.disconnect(websocket, connection_id)
        logger.info(f"Client disconnected from {agent_name}")
    except Exception as e:
        logger.error(f"Agent WebSocket error: {e}")
        manager.disconnect(websocket, connection_id)
