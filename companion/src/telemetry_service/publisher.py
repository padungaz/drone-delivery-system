import logging
from datetime import datetime, timezone

from src.mavlink_service.controller import MavlinkController
from src.state_machine.machine import StateMachine

logger = logging.getLogger(__name__)


class TelemetryPublisher:
    """Builds and publishes telemetry payload every 2 seconds."""

    def __init__(
        self,
        mavlink: MavlinkController,
        state_machine: StateMachine,
        aruco_detected: callable = lambda: False,
        landing_status: callable = lambda: "NONE",
    ):
        self.mavlink = mavlink
        self.state_machine = state_machine
        self._aruco_detected = aruco_detected
        self._landing_status = landing_status

    def build_payload(self) -> dict:
        t = self.mavlink.telemetry
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "drone_id": __import__("config").DRONE_ID,
            "drone_state": self.state_machine.state_name,
            "latitude": t.latitude,
            "longitude": t.longitude,
            "altitude_relative": t.altitude_relative,
            "altitude_agl": t.altitude_agl,
            "rangefinder_valid": t.rangefinder_valid,
            "battery": t.battery,
            "ground_speed": t.ground_speed,
            "heading": t.heading,
            "gps_satellite": t.gps_satellite,
            "flight_mode": t.flight_mode,
            "aruco_detected": self._aruco_detected(),
            "landing_status": self._landing_status(),
            "armed": t.armed,
        }
