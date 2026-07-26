import logging
from typing import Dict, Any, Optional

from app.models.schemas import TelemetryPayload, DroneState

logger = logging.getLogger(__name__)


class DroneManager:
    """Manager for UAV Drone Telemetry & Mission State Machine."""

    _instance: Optional["DroneManager"] = None

    def __init__(self):
        self.telemetry_store: Dict[str, TelemetryPayload] = {}

    @classmethod
    def get_instance(cls) -> "DroneManager":
        if cls._instance is None:
            cls._instance = DroneManager()
        return cls._instance

    def update_telemetry(self, telemetry: TelemetryPayload) -> None:
        self.telemetry_store[telemetry.drone_id] = telemetry
        logger.debug("Updated telemetry for %s: state=%s, lat=%f, lon=%f", telemetry.drone_id, telemetry.drone_state, telemetry.latitude, telemetry.longitude)

    def get_latest_telemetry(self, drone_id: str = "UAV01") -> Optional[TelemetryPayload]:
        return self.telemetry_store.get(drone_id) or self.telemetry_store.get("drone-01")

    def get_drone_state(self, drone_id: str = "UAV01") -> str:
        t = self.get_latest_telemetry(drone_id)
        return t.drone_state.value if t else "IDLE"


drone_manager = DroneManager.get_instance()
