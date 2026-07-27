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
    CAMERA_START = "CAMERA_START"
    CAMERA_STOP = "CAMERA_STOP"


class MissionCommand(BaseModel):
    action: MissionAction
    home_lat: float
    home_lon: float
    pickup_lat: float
    pickup_lon: float


class StepCommandRequest(BaseModel):
    step_action: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    alt: Optional[float] = None
    drone_id: str = "drone-01"
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


# ---------------------------------------------------------------------------
# Customer / Delivery Request schemas (new)
# ---------------------------------------------------------------------------

class WarehouseConfigResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    address_text: str
    updated_at: datetime


class WarehouseConfigUpdate(BaseModel):
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address_text: Optional[str] = None


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    phone: str = Field(..., min_length=6, max_length=32)


class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: str
    created_at: datetime


class CustomerAddressCreate(BaseModel):
    customer_id: int
    address_type: str = Field(default="RECEIVE", pattern="^(RECEIVE|SEND)$")
    address_name: str = Field(..., min_length=1, max_length=128)
    address_text: str = Field(..., min_length=1, max_length=256)
    latitude: float
    longitude: float


class CustomerAddressUpdate(BaseModel):
    address_type: Optional[str] = Field(default=None, pattern="^(RECEIVE|SEND)$")
    address_name: Optional[str] = None
    address_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CustomerAddressResponse(BaseModel):
    id: int
    customer_id: int
    address_type: str
    address_name: str
    address_text: str
    latitude: float
    longitude: float
    created_at: datetime


class DeliveryType(str, Enum):
    RECEIVE_FROM_WAREHOUSE = "RECEIVE_FROM_WAREHOUSE"
    SEND_TO_WAREHOUSE = "SEND_TO_WAREHOUSE"


class DeliveryStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    FLYING = "FLYING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class DeliveryRequestCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=128)
    customer_phone: str = Field(..., min_length=6, max_length=32)
    delivery_type: DeliveryType
    # Customer's address (pickup if RECEIVE, drop if SEND)
    customer_lat: float
    customer_lon: float
    customer_address: str = ""
    note: str = ""


class DeliveryRequestResponse(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    customer_phone: str
    delivery_type: str
    pickup_lat: float
    pickup_lon: float
    pickup_address: str
    drop_lat: float
    drop_lon: float
    drop_address: str
    status: str
    mission_id: Optional[int]
    note: str
    created_at: datetime
    updated_at: datetime


class DeliveryStatusUpdate(BaseModel):
    status: DeliveryStatus
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Smart Intralogistics Schemas (Device, PLC, Robot, Inventory, Mission)
# ---------------------------------------------------------------------------

class DeviceType(str, Enum):
    UAV = "UAV"
    PLC = "PLC"
    ROBOT = "ROBOT"
    CAMERA = "CAMERA"


class DeviceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    BUSY = "BUSY"
    ERROR = "ERROR"


class DeviceRegisterRequest(BaseModel):
    name: str = Field(..., description="Device name, e.g. UAV01, PLC01, ROBOT01, CAM01")
    type: DeviceType
    ip: str = Field(..., description="IP Address on LAN network")


class DeviceHeartbeatRequest(BaseModel):
    name: str
    status: DeviceStatus = DeviceStatus.ONLINE


class DeviceResponse(BaseModel):
    id: int
    device_name: str
    device_type: str
    ip_address: str
    status: str
    last_heartbeat: datetime
    created_at: datetime


class PLCCommand(str, Enum):
    LOCK_DRONE = "LOCK_DRONE"
    UNLOCK_DRONE = "UNLOCK_DRONE"
    Z_UP = "Z_UP"
    Z_DOWN = "Z_DOWN"


class PLCCommandRequest(BaseModel):
    command: PLCCommand


class PLCStatusResponse(BaseModel):
    drone_detected: bool = False
    clamp_x: str = "OPEN"       # "OPEN", "LOCKING", "DONE"
    clamp_y: str = "OPEN"       # "OPEN", "LOCKING", "DONE"
    drone_locked: bool = False
    z_axis: str = "HOME"        # "HOME", "UP", "DOWN"


class RobotCommand(str, Enum):
    MOVE_HOME = "MOVE_HOME"
    PICK_PRODUCT = "PICK_PRODUCT"
    PLACE_PRODUCT = "PLACE_PRODUCT"
    REQUEST_Z_UP = "REQUEST_Z_UP"
    REQUEST_Z_DOWN = "REQUEST_Z_DOWN"
    PICK = "PICK"
    STORE = "STORE"


class RobotCommandRequest(BaseModel):
    command: RobotCommand
    slot: Optional[str] = None   # e.g. "B2"


class RobotStatusResponse(BaseModel):
    state: str = "IDLE"          # "IDLE", "READY", "MOVING", "PICKING", "PLACING", "ERROR"
    current_slot: Optional[str] = None
    holding_product: Optional[str] = None


class StorageSlotStatus(str, Enum):
    EMPTY = "EMPTY"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"


class StorageSlotResponse(BaseModel):
    id: int
    slot_name: str
    status: str
    product_id: Optional[str] = None
    qr_code: Optional[str] = None
    updated_time: datetime


class StorageSlotUpdateRequest(BaseModel):
    status: StorageSlotStatus
    product_id: Optional[str] = None
    qr_code: Optional[str] = None


class QRScanPayload(BaseModel):
    camera_id: str = "CAM01"
    qr: str
    time: datetime = Field(default_factory=datetime.utcnow)


class IntralogisticsMissionType(str, Enum):
    DRONE_PICKUP = "DRONE_PICKUP"
    DRONE_DELIVERY = "DRONE_DELIVERY"


class IntralogisticsMissionCreate(BaseModel):
    drone_id: str = "UAV01"
    task: str = "PICKUP"         # "PICKUP" or "DELIVERY"
    product_id: str


class IntralogisticsMissionResponse(BaseModel):
    id: int
    mission_type: str
    drone_id: str
    product_id: str
    target_slot: Optional[str] = None
    state: str
    step_details: str
    created_at: datetime
    updated_at: datetime


