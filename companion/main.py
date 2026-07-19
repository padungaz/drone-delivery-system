#!/usr/bin/env python3
"""
Drone Delivery Companion — Raspberry Pi 5 main entry point.

Deployment:  Raspberry Pi 5 (headless, VS Code Remote SSH)
Connection:  Pi → MAVLink UART → Pixhawk 6C (PX4)
             Pi → WebSocket → FastAPI Backend (LAN)

Run:
    python main.py

Auto-start:
    sudo systemctl enable drone-companion
    sudo systemctl start drone-companion
"""

import asyncio
import logging
import signal
import socket
import sys
import time

import config
from src.mavlink_service.factory import create_mavlink_controller
from src.mission_manager.manager import MissionManager
from src.network_service.websocket_client import WebSocketClient
from src.telemetry_service.publisher import TelemetryPublisher
from src.vision_service.aruco_landing import ArucoLandingService

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
if config.LOG_FILE:
    try:
        handlers.append(logging.FileHandler(config.LOG_FILE))
    except OSError as e:
        # Cannot write to log file (permissions); stdout only
        print(f"[WARNING] Cannot open log file {config.LOG_FILE}: {e}", file=sys.stderr)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers,
)
logger = logging.getLogger("companion")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_pi_ip() -> str:
    """Return the primary LAN IP of this Raspberry Pi."""
    try:
        # Connect to the backend server address to resolve the correct interface
        with socket.create_connection((config.SERVER_IP, config.SERVER_PORT), timeout=2):
            pass
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((config.SERVER_IP, 1))
        return s.getsockname()[0]
    except Exception:
        return "unknown"


def _log_startup_info() -> None:
    """Print hardware / network context on startup."""
    hostname = socket.gethostname()
    pi_ip    = _get_pi_ip()

    logger.info("=" * 60)
    logger.info("Drone Delivery Companion — Raspberry Pi 5")
    logger.info("=" * 60)
    logger.info("[INFO] Pi hostname  : %s", hostname)
    logger.info("[INFO] Pi IP        : %s", pi_ip)
    logger.info("[INFO] Drone ID     : %s", config.DRONE_ID)
    logger.info("[INFO] MAVLink dev  : %s  @ %d baud", config.MAVLINK_DEVICE, config.MAVLINK_BAUD)
    logger.info("[INFO] Backend      : http://%s:%d", config.SERVER_IP, config.SERVER_PORT)
    logger.info("[INFO] WebSocket    : %s", config.WS_URL)
    logger.info("[INFO] Log file     : %s", config.LOG_FILE or "stdout only")
    logger.info("[INFO] Mission state: IDLE")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CompanionApp
# ---------------------------------------------------------------------------

class CompanionApp:
    def __init__(self):
        self.mavlink        = create_mavlink_controller()
        self.vision         = ArucoLandingService()
        self.ws             = WebSocketClient()
        self.mission: MissionManager | None        = None
        self.telemetry_pub: TelemetryPublisher | None = None
        self._running           = True
        self._last_telemetry_send = 0.0

    # ------------------------------------------------------------------
    # MAVLink connect with auto-retry
    # ------------------------------------------------------------------

    def _connect_mavlink(self) -> bool:
        """
        Try to connect MAVLink.  Retry forever with delay until success
        or shutdown signal.
        """
        attempt = 0
        while self._running:
            attempt += 1
            logger.info(
                "[INFO] MAVLink connect attempt %d → %s @ %d baud",
                attempt,
                config.MAVLINK_DEVICE,
                config.MAVLINK_BAUD,
            )
            if self.mavlink.connect():
                logger.info("[INFO] PX4 heartbeat received — MAVLink connected")
                return True
            logger.warning(
                "[WARNING] MAVLink connection failed (attempt %d) — retrying in %.0fs",
                attempt,
                config.MAVLINK_RECONNECT_DELAY_SEC,
            )
            time.sleep(config.MAVLINK_RECONNECT_DELAY_SEC)
        return False

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        if not self._connect_mavlink():
            return False

        self.mission = MissionManager(self.mavlink, self.vision, self.ws)
        self.ws._on_command = self.mission.handle_command

        self.telemetry_pub = TelemetryPublisher(
            self.mavlink,
            self.mission.state_machine,
            aruco_detected=self.mission.get_aruco_detected,
            landing_status=self.mission.get_landing_status,
        )
        logger.info("[INFO] Companion setup complete")
        return True

    # ------------------------------------------------------------------
    # Async tasks
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        self._running = False
        if self.mission:
            self.mission.get_camera_service().stop()
            self.mission.shutdown()
        self.vision.stop()
        self.ws.stop()
        logger.info("[INFO] Companion shutdown complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    _log_startup_info()

    app = CompanionApp()

    def signal_handler(sig, frame):
        logger.info("[INFO] Signal %s received — shutting down...", sig)
        app.shutdown()

    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not app.setup():
        logger.error("[ERROR] Companion setup failed — exiting")
        sys.exit(1)

    # Pass event loop to mission manager for thread-safe async callbacks
    if app.mission:
        app.mission.set_event_loop(asyncio.get_running_loop())

    await asyncio.gather(
        app.run_ws_listener(),
        app.run_main_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
