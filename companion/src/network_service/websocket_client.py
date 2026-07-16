"""
WebSocket client — kết nối Raspberry Pi tới FastAPI Backend qua LAN.

URL:  ws://SERVER_IP:8000/ws/drone/drone-01
Auto-reconnect với delay WS_RECONNECT_DELAY_SEC.
"""

import asyncio
import json
import logging
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

import config

logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client với auto-reconnect tới FastAPI backend."""

    def __init__(self, on_command: Optional[Callable[[dict], None]] = None):
        self.url = config.WS_URL
        self._on_command       = on_command
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected        = False
        self._reconnect_attempts = 0
        self._should_run       = True

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        while self._should_run:
            try:
                logger.info(
                    "[INFO] WebSocket connecting to %s (attempt %d)...",
                    self.url,
                    self._reconnect_attempts + 1,
                )
                self._ws = await websockets.connect(self.url)
                self._connected = True
                self._reconnect_attempts = 0
                logger.info("[INFO] WebSocket connected to %s", self.url)
                return True

            except Exception as exc:
                self._reconnect_attempts += 1
                logger.warning(
                    "[WARNING] WebSocket connect failed (attempt %d): %s — retrying in %.0fs",
                    self._reconnect_attempts,
                    exc,
                    config.WS_RECONNECT_DELAY_SEC,
                )
                if (
                    config.WS_MAX_RECONNECT_ATTEMPTS > 0
                    and self._reconnect_attempts >= config.WS_MAX_RECONNECT_ATTEMPTS
                ):
                    logger.error(
                        "[ERROR] WebSocket max reconnect attempts (%d) reached",
                        config.WS_MAX_RECONNECT_ATTEMPTS,
                    )
                    return False
                await asyncio.sleep(config.WS_RECONNECT_DELAY_SEC)
        return False

    async def listen(self) -> None:
        while self._should_run:
            if not self._connected or self._ws is None:
                await self.connect()
                continue

            try:
                message = await self._ws.recv()
                data = json.loads(message)
                if data.get("type") == "command" and self._on_command:
                    self._on_command(data.get("payload", {}))

            except ConnectionClosed:
                logger.warning(
                    "[WARNING] WebSocket disconnected from %s — reconnecting in %.0fs",
                    self.url,
                    config.WS_RECONNECT_DELAY_SEC,
                )
                self._connected = False
                await asyncio.sleep(config.WS_RECONNECT_DELAY_SEC)

            except Exception as exc:
                logger.error("[ERROR] WebSocket listen error: %s", exc)
                self._connected = False
                await asyncio.sleep(config.WS_RECONNECT_DELAY_SEC)

    async def send(self, message: dict) -> bool:
        if not self._connected or self._ws is None:
            return False
        try:
            await self._ws.send(json.dumps(message))
            return True
        except Exception as exc:
            logger.error("[ERROR] WebSocket send failed: %s", exc)
            self._connected = False
            return False

    async def send_telemetry(self, payload: dict) -> bool:
        return await self.send({"type": "telemetry", "payload": payload})

    async def send_error(self, source: str, message: str) -> bool:
        return await self.send({
            "type": "error",
            "payload": {"source": source, "message": message},
        })

    async def send_landing_result(
        self,
        location_type: str,
        success: bool,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> bool:
        return await self.send({
            "type": "landing_result",
            "payload": {
                "location_type": location_type,
                "success":       success,
                "offset_x":      offset_x,
                "offset_y":      offset_y,
            },
        })

    async def send_camera_status(self, status: str, device: str) -> bool:
        """Send camera ON/OFF/ERROR status to backend."""
        return await self.send({
            "type": "camera_status",
            "payload": {"camera": status, "device": device},
        })

    async def send_aruco_detection(self, payload: dict) -> bool:
        """Send ArUco detection result to backend."""
        return await self.send({
            "type": "aruco_detection",
            "payload": payload,
        })

    def stop(self) -> None:
        self._should_run = False
        if self._ws:
            asyncio.create_task(self._ws.close())
        logger.info("[INFO] WebSocket client stopped")

