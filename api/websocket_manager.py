"""
WebSocket Manager for Real-Time Agent Streaming
Provides real-time updates on agent execution via WebSocket connections
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, Optional, Any
import asyncio
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self):
        # Active connections per analysis_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Broadcast connections (all analyses)
        self.broadcast_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, analysis_id: Optional[str] = None):
        """Accept new WebSocket connection"""
        await websocket.accept()

        if analysis_id:
            if analysis_id not in self.active_connections:
                self.active_connections[analysis_id] = set()
            self.active_connections[analysis_id].add(websocket)
            logger.info(f"WebSocket connected for analysis {analysis_id}")
        else:
            self.broadcast_connections.add(websocket)
            logger.info("WebSocket connected for broadcast")

    def disconnect(self, websocket: WebSocket, analysis_id: Optional[str] = None):
        """Remove WebSocket connection"""
        if analysis_id and analysis_id in self.active_connections:
            self.active_connections[analysis_id].discard(websocket)
            if not self.active_connections[analysis_id]:
                del self.active_connections[analysis_id]
            logger.info(f"WebSocket disconnected from analysis {analysis_id}")
        else:
            self.broadcast_connections.discard(websocket)
            logger.info("WebSocket disconnected from broadcast")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def send_to_analysis(self, analysis_id: str, message: Dict[str, Any]):
        """Send message to all connections for specific analysis"""
        if analysis_id in self.active_connections:
            message_json = json.dumps(message, default=str)
            disconnected = []

            for connection in self.active_connections[analysis_id]:
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    logger.error(f"Error sending to analysis {analysis_id}: {e}")
                    disconnected.append(connection)

            # Clean up disconnected
            for conn in disconnected:
                self.disconnect(conn, analysis_id)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        message_json = json.dumps(message, default=str)
        disconnected = []

        for connection in self.broadcast_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
                disconnected.append(connection)

        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn)

    async def send_agent_status(
        self,
        analysis_id: str,
        agent_name: str,
        status: str,
        progress: float,
        message: str = ""
    ):
        """Send agent execution status update"""
        update = {
            "type": "agent_status",
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_id": analysis_id,
            "agent_name": agent_name,
            "status": status,
            "progress": progress,
            "message": message
        }
        await self.send_to_analysis(analysis_id, update)

    async def send_phase_status(
        self,
        analysis_id: str,
        phase: str,
        status: str,
        agents_completed: int,
        total_agents: int
    ):
        """Send phase execution status update"""
        update = {
            "type": "phase_status",
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_id": analysis_id,
            "phase": phase,
            "status": status,
            "progress": (agents_completed / total_agents * 100) if total_agents > 0 else 0,
            "agents_completed": agents_completed,
            "total_agents": total_agents
        }
        await self.send_to_analysis(analysis_id, update)

    async def send_analysis_complete(
        self,
        analysis_id: str,
        success: bool,
        summary: str,
        execution_time_ms: float
    ):
        """Send analysis completion notification"""
        update = {
            "type": "analysis_complete",
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_id": analysis_id,
            "success": success,
            "summary": summary,
            "execution_time_ms": execution_time_ms
        }
        await self.send_to_analysis(analysis_id, update)

    async def send_finding(
        self,
        analysis_id: str,
        agent_name: str,
        finding: Dict[str, Any]
    ):
        """Send individual finding as it's discovered"""
        update = {
            "type": "finding",
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_id": analysis_id,
            "agent_name": agent_name,
            "finding": finding
        }
        await self.send_to_analysis(analysis_id, update)

    async def send_error(
        self,
        analysis_id: str,
        agent_name: str,
        error: str
    ):
        """Send error notification"""
        update = {
            "type": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_id": analysis_id,
            "agent_name": agent_name,
            "error": error
        }
        await self.send_to_analysis(analysis_id, update)


# Global connection manager instance
manager = ConnectionManager()
