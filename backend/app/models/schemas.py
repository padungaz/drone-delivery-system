from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DroneState(str, Enum):
    # Ground / idle
    IDLE = "IDLE"

    # Initial mission: arm → takeoff → fly to pickup → descend → search → land
    ARMING = "ARMING"
    TAKEOFF = "TAKEOFF"
    FLY_TO_PICKUP = "FLY_TO_PICKUP"
    DESCEND = "DESCEND"
    SEARCH_ARUCO = "SEARCH_ARUCO"
    PRECISION_LANDING = "PRECISION_LANDING"

    # User confirm gate at pickup (drone is on ground, disarmed)
    WAIT_PICKUP_CONFIRM = "WAIT_PICKUP_CONFIRM"

    # After pickup confirm: arm → takeoff → fly to drop → descend → search → land
    FLY_TO_DROP = "FLY_TO_DROP"

    # User confirm gate at drop (drone is on ground, disarmed)
    WAIT_DROP_CONFIRM = "WAIT_DROP_CONFIRM"

    # After drop confirm: arm → takeoff → RTL → auto-land → auto-disarm → IDLE
    RETURN_HOME = "RETURN_HOME"

    ERROR = "ERROR"

    # Legacy states kept for backward-compatibility with existing DB rows
    # Do NOT use these in new mission logic
    PICKUP = "PICKUP"
    DROP_PACKAGE = "DROP_PACKAGE"
    RTL = "RTL"
    LAND = "LAND"
    DISARM = "DISARM"
    LANDING = "LANDING"


class MissionAction(str, Enum):
    START = "START"
    START_MISSION = "START_MISSION"
    PICKUP_COMPLETE = "PICKUP_COMPLETE"
    DROP_COMPLETE = "DROP_COMPLETE"
    FORCE_RTL = "FORCE_RTL"
    STOP = "STOP"


class Location(BaseModel):
    lat: float
    lon: float


class MissionCommand(BaseModel):
    action: MissionAction
    home_lat: float
    home_lon: float
    pickup_lat: float
    pickup_lon: float
    drop_lat: float
    drop_lon: float
    drone_id: str = "drone-01"


class TelemetryPayload(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    drone_id: str = "drone-01"
    drone_state: DroneState = DroneState.IDLE
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_relative: float = 0.0
    altitude_agl: float = 0.0
    battery: float = 100.0
    ground_speed: float = 0.0
    heading: float = 0.0
    gps_satellite: int = 0
    flight_mode: str = "UNKNOWN"
    aruco_detected: bool = False
    landing_status: str = "NONE"
    landing_phase: str = "none"   # "pickup" | "drop" | "rtl" | "none"
    armed: bool = False


class DroneStatusResponse(BaseModel):
    drone_id: str
    connected: bool
    last_telemetry: Optional[TelemetryPayload] = None
    can_stop: bool = False


class MissionHistoryItem(BaseModel):
    id: int
    drone_id: str
    action: str
    home_lat: float
    home_lon: float
    pickup_lat: float
    pickup_lon: float
    drop_lat: float
    drop_lon: float
    status: str
    created_at: datetime


class WebSocketMessage(BaseModel):
    type: str
    payload: dict
