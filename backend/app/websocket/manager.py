import logging
from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class SystemWebSocketManager:
    """Manages WebSocket connections for `/ws/system` realtime updates across devices, dashboard, and systems."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("System WebSocket client connected. Total clients: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("System WebSocket client disconnected. Total clients: %d", len(self.active_connections))

    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast event message to all connected clients.
        Example message:
        {
            "type": "PLC_STATUS",
            "data": { "drone_locked": True }
        }
        """
        payload = {
            "type": event_type,
            "data": data,
        }
        dead_sockets: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception as exc:
                logger.error("Error sending WebSocket message: %s", exc)
                dead_sockets.append(connection)

        for dead in dead_sockets:
            self.disconnect(dead)


system_ws_manager = SystemWebSocketManager()
