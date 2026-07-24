"""
WebSocket Client — Nhận real-time storage updates từ Backend.

Kết nối tới ws://<SERVER>/ws/client và lắng nghe event 'storage_update'.
"""

import asyncio
import json
import logging
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

import config

logger = logging.getLogger(__name__)


class StorageWSClient:
    """WebSocket client kết nối tới Backend để nhận storage_update events."""

    def __init__(
        self,
        on_storage_update: Optional[Callable[[dict], None]] = None,
    ):
        """
        Args:
            on_storage_update: Callback khi nhận event storage_update.
                               Nhận dict chứa payload trạng thái kho.
        """
        self.on_storage_update = on_storage_update
        self._running = False

    async def connect(self) -> None:
        """Kết nối WebSocket và lắng nghe events. Tự động reconnect."""
        self._running = True
        url = config.WS_URL

        while self._running:
            try:
                logger.info("Connecting WebSocket to %s", url)

                async with websockets.connect(url) as ws:
                    logger.info("WebSocket connected")

                    async for message in ws:
                        try:
                            data = json.loads(message)
                            msg_type = data.get("type", "")

                            if msg_type == "storage_update":
                                payload = data.get("payload", {})
                                logger.debug("Storage update received")
                                if self.on_storage_update:
                                    self.on_storage_update(payload)

                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON from WebSocket")

            except ConnectionClosedOK:
                logger.info("WebSocket closed normally")
            except ConnectionClosedError as exc:
                logger.warning("WebSocket closed with error: %s", exc)
            except ConnectionRefusedError:
                logger.warning(
                    "WebSocket connection refused. Server offline? Retrying..."
                )
            except OSError as exc:
                logger.warning("WebSocket connection error: %s", exc)
            except Exception as exc:
                logger.error("WebSocket unexpected error: %s", exc)

            if self._running:
                logger.info(
                    "Reconnecting in %.1f seconds...",
                    config.WS_RECONNECT_DELAY_SEC,
                )
                await asyncio.sleep(config.WS_RECONNECT_DELAY_SEC)

    def stop(self) -> None:
        """Dừng WebSocket client."""
        self._running = False
        logger.info("WebSocket client stopping")
