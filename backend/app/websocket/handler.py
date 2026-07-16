import json
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.database.repository import Repository
from app.models.schemas import MissionAction, MissionCommand, TelemetryPayload
from app.services.drone_service import drone_service

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for drones and client dashboards."""

    def __init__(self):
        self.drone_connections: dict[str, WebSocket] = {}
        self.client_connections: list[WebSocket] = []

    async def connect_drone(self, websocket: WebSocket, drone_id: str) -> None:
        await websocket.accept()
        self.drone_connections[drone_id] = websocket
        logger.info("Drone connected: %s", drone_id)
        await self.broadcast_to_clients(
            {"type": "drone_connected", "payload": {"drone_id": drone_id}}
        )

    async def disconnect_drone(self, drone_id: str) -> None:
        self.drone_connections.pop(drone_id, None)
        logger.info("Drone disconnected: %s", drone_id)
        await self.broadcast_to_clients(
            {"type": "drone_disconnected", "payload": {"drone_id": drone_id}}
        )

    async def connect_client(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.client_connections.append(websocket)
        logger.info("Client connected. Total clients: %d", len(self.client_connections))

    def disconnect_client(self, websocket: WebSocket) -> None:
        if websocket in self.client_connections:
            self.client_connections.remove(websocket)
        logger.info("Client disconnected. Total clients: %d", len(self.client_connections))

    async def broadcast_to_clients(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self.client_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_client(ws)

    async def send_to_drone(self, drone_id: str, message: dict) -> bool:
        ws = self.drone_connections.get(drone_id)
        if ws is None:
            logger.warning("Drone %s not connected", drone_id)
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception as exc:
            logger.error("Failed to send to drone %s: %s", drone_id, exc)
            return False

    def is_drone_connected(self, drone_id: str) -> bool:
        return drone_id in self.drone_connections


manager = ConnectionManager()


async def handle_drone_websocket(
    websocket: WebSocket,
    drone_id: str,
    repo: Repository,
) -> None:
    await manager.connect_drone(websocket, drone_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                msg_type = payload.get("type", "telemetry")

                if msg_type == "telemetry":
                    telemetry = TelemetryPayload(**payload.get("payload", payload))
                    telemetry.drone_id = drone_id
                    drone_service.update_telemetry(telemetry)
                    await repo.upsert_drone_status(telemetry)
                    await repo.log_telemetry(telemetry)
                    await manager.broadcast_to_clients(
                        {"type": "telemetry", "payload": telemetry.model_dump(mode="json")}
                    )
                elif msg_type == "landing_result":
                    p = payload.get("payload", {})
                    await repo.log_landing_result(
                        drone_id=drone_id,
                        location_type=p.get("location_type", "unknown"),
                        success=p.get("success", False),
                        offset_x=p.get("offset_x", 0.0),
                        offset_y=p.get("offset_y", 0.0),
                        mission_id=p.get("mission_id"),
                    )
                elif msg_type == "error":
                    p = payload.get("payload", {})
                    await repo.log_error(
                        drone_id=drone_id,
                        source=p.get("source", "companion"),
                        message=p.get("message", "Unknown error"),
                    )
                    await manager.broadcast_to_clients(
                        {"type": "error", "payload": {"drone_id": drone_id, **p}}
                    )
                elif msg_type == "camera_status":
                    # Broadcast camera ON/OFF/ERROR status to all frontend clients
                    p = payload.get("payload", {})
                    await manager.broadcast_to_clients(
                        {"type": "camera_status", "payload": {"drone_id": drone_id, **p}}
                    )
                    logger.info("Camera status from %s: %s", drone_id, p.get("camera"))
                elif msg_type == "aruco_detection":
                    # Broadcast ArUco detection result to all frontend clients
                    p = payload.get("payload", {})
                    await manager.broadcast_to_clients(
                        {"type": "aruco_detection", "payload": {"drone_id": drone_id, **p}}
                    )
            except Exception as exc:
                logger.error("Invalid message from drone %s: %s", drone_id, exc)
    except WebSocketDisconnect:
        await manager.disconnect_drone(drone_id)
        await repo.mark_drone_disconnected(drone_id)


async def handle_client_websocket(websocket: WebSocket) -> None:
    await manager.connect_client(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_client(websocket)


async def forward_mission_to_drone(command: MissionCommand) -> bool:
    message = {
        "type": "command",
        "payload": command.model_dump(),
    }
    return await manager.send_to_drone(command.drone_id, message)
