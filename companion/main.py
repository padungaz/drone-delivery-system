#!/usr/bin/env python3
"""Drone Delivery Companion — Raspberry Pi 5 main entry point."""

import asyncio
import logging
import signal
import sys
import time

import config
from src.mavlink_service.factory import create_mavlink_controller
from src.mission_manager.manager import MissionManager
from src.network_service.websocket_client import WebSocketClient
from src.telemetry_service.publisher import TelemetryPublisher
from src.vision_service.aruco_landing import ArucoLandingService

handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
if config.LOG_FILE:
    try:
        handlers.append(logging.FileHandler(config.LOG_FILE))
    except OSError:
        pass

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers,
)
logger = logging.getLogger("companion")


class CompanionApp:
    def __init__(self):
        self.mavlink = create_mavlink_controller()
        self.vision = ArucoLandingService()
        self.ws = WebSocketClient()
        self.mission: MissionManager | None = None
        self.telemetry_pub: TelemetryPublisher | None = None
        self._running = True
        self._last_telemetry_send = 0.0

    def setup(self) -> bool:
        if not self.mavlink.connect():
            logger.error("Failed to connect MAVLink")
            return False

        self.mission = MissionManager(self.mavlink, self.vision, self.ws)
        self.ws._on_command = self.mission.handle_command

        self.telemetry_pub = TelemetryPublisher(
            self.mavlink,
            self.mission.state_machine,
            aruco_detected=self.mission.get_aruco_detected,
            landing_status=self.mission.get_landing_status,
        )
        logger.info("Companion setup complete")
        return True

    async def run_ws_listener(self) -> None:
        await self.ws.connect()
        await self.ws.listen()

    async def run_main_loop(self) -> None:
        loop_interval = 1.0 / config.MAVLINK_POLL_RATE_HZ

        while self._running:
            if self.mission:
                self.mission.tick()

            now = time.time()
            if (
                self.telemetry_pub
                and now - self._last_telemetry_send >= config.TELEMETRY_INTERVAL_SEC
            ):
                payload = self.telemetry_pub.build_payload()
                await self.ws.send_telemetry(payload)
                self._last_telemetry_send = now

            await asyncio.sleep(loop_interval)

    def shutdown(self) -> None:
        self._running = False
        self.vision.stop()
        self.ws.stop()
        logger.info("Companion shutdown")


async def main():
    app = CompanionApp()

    def signal_handler(sig, frame):
        logger.info("Signal received, shutting down...")
        app.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not app.setup():
        sys.exit(1)

    await asyncio.gather(
        app.run_ws_listener(),
        app.run_main_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
