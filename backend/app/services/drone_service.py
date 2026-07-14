import logging
from typing import Optional

from fastapi import HTTPException

from app.database.repository import Repository, can_stop_drone
from app.models.schemas import (
    DroneState,
    DroneStatusResponse,
    MissionAction,
    MissionCommand,
    MissionHistoryItem,
    TelemetryPayload,
)

logger = logging.getLogger(__name__)

# States where the drone is actively flying (airborne)
# WAIT_PICKUP_CONFIRM and WAIT_DROP_CONFIRM are intentionally excluded —
# drone is on the ground (landed, disarmed) during those states.
FLYING_STATES = {
    DroneState.ARMING,
    DroneState.TAKEOFF,
    DroneState.FLY_TO_PICKUP,
    DroneState.DESCEND,
    DroneState.SEARCH_ARUCO,
    DroneState.PRECISION_LANDING,
    DroneState.FLY_TO_DROP,
    DroneState.RETURN_HOME,
    # Legacy
    DroneState.LANDING,
    DroneState.RTL,
}

# States where the START button should be enabled on the frontend
START_ENABLED_STATES = {
    DroneState.IDLE,
    DroneState.RETURN_HOME,  # Continuous Delivery Mode
}


class DroneService:
    def __init__(self):
        self._latest_telemetry: dict[str, TelemetryPayload] = {}

    def update_telemetry(self, telemetry: TelemetryPayload) -> None:
        self._latest_telemetry[telemetry.drone_id] = telemetry

    def get_telemetry(self, drone_id: str) -> Optional[TelemetryPayload]:
        return self._latest_telemetry.get(drone_id)

    async def get_status(self, repo: Repository, drone_id: str) -> DroneStatusResponse:
        record = await repo.get_drone_status(drone_id)
        telemetry = self.get_telemetry(drone_id)
        if record is None and telemetry is None:
            return DroneStatusResponse(
                drone_id=drone_id,
                connected=False,
                can_stop=False,
            )

        state = telemetry.drone_state.value if telemetry else record.drone_state
        armed = telemetry.armed if telemetry else record.armed
        return DroneStatusResponse(
            drone_id=drone_id,
            connected=record.connected if record else True,
            last_telemetry=telemetry,
            can_stop=can_stop_drone(state, armed),
        )

    def validate_stop(self, telemetry: Optional[TelemetryPayload]) -> None:
        """STOP is only allowed when drone is on the ground and disarmed."""
        if telemetry is None:
            raise HTTPException(status_code=400, detail="No telemetry available")

        if telemetry.drone_state in FLYING_STATES:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot STOP while drone is airborne (state: {telemetry.drone_state.value})",
            )
        if telemetry.armed:
            raise HTTPException(status_code=400, detail="Cannot STOP while motors are armed")

        # Allow STOP from IDLE, WAIT_PICKUP_CONFIRM, WAIT_DROP_CONFIRM, ERROR
        allowed = {
            DroneState.IDLE,
            DroneState.WAIT_PICKUP_CONFIRM,
            DroneState.WAIT_DROP_CONFIRM,
            DroneState.ERROR,
        }
        if telemetry.drone_state not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"STOP not allowed in state {telemetry.drone_state.value}",
            )

    def can_start(self, telemetry: Optional[TelemetryPayload]) -> bool:
        """Returns True if START command should be accepted."""
        if telemetry is None:
            return False
        return telemetry.drone_state in START_ENABLED_STATES


class MissionService:
    @staticmethod
    def build_start_command(command: MissionCommand) -> MissionCommand:
        return MissionCommand(
            action=MissionAction.START_MISSION,
            home_lat=command.home_lat,
            home_lon=command.home_lon,
            pickup_lat=command.pickup_lat,
            pickup_lon=command.pickup_lon,
            drop_lat=command.drop_lat,
            drop_lon=command.drop_lon,
            drone_id=command.drone_id,
        )

    @staticmethod
    async def get_history(repo: Repository) -> list[MissionHistoryItem]:
        records = await repo.get_mission_history()
        return [
            MissionHistoryItem(
                id=r.id,
                drone_id=r.drone_id,
                action=r.action,
                home_lat=r.home_lat,
                home_lon=r.home_lon,
                pickup_lat=r.pickup_lat,
                pickup_lon=r.pickup_lon,
                drop_lat=r.drop_lat,
                drop_lon=r.drop_lon,
                status=r.status,
                created_at=r.created_at,
            )
            for r in records
        ]


drone_service = DroneService()
mission_service = MissionService()
