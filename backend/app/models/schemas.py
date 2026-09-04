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
    PICKUP_COMPLETE = "PICKUP_COMPLETE"
    DROP_COMPLETE = "DROP_COMPLETE"
    FORCE_RTL = "FORCE_RTL"
    STOP = "STOP"
    CAMERA_START = "CAMERA_START"
    CAMERA_STOP = "CAMERA_STOP"


class MissionCommand(BaseModel):
    action: MissionAction
    home_lat: float = 0.0
    home_lon: float = 0.0
    pickup_lat: float = 0.0
    pickup_lon: float = 0.0
    drop_lat: float = 0.0
    drop_lon: float = 0.0
    drone_id: str = "drone-01"


class StepCommandRequest(BaseModel):
    step_action: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    alt: Optional[float] = None
    drop_lat: Optional[float] = None
    drop_lon: Optional[float] = None
    drone_id: str = "drone-01"


class LandingLocation(str, Enum):
    WAREHOUSE_PAD = "WAREHOUSE_PAD"
    CUSTOMER_PICKUP = "CUSTOMER_PICKUP"
    CUSTOMER_DROP = "CUSTOMER_DROP"
    UNKNOWN = "UNKNOWN"


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
    landing_location: LandingLocation = LandingLocation.WAREHOUSE_PAD
    armed: bool = False


class LandingResultPayload(BaseModel):
    drone_id: str = "drone-01"
    location_type: LandingLocation = LandingLocation.WAREHOUSE_PAD
    success: bool = True
    offset_x: float = 0.0
    offset_y: float = 0.0
    mission_id: Optional[int] = None



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
    port: Optional[int] = 8090
    simulator_mode: Optional[bool] = False
    rack: Optional[int] = 0
    slot: Optional[int] = 1
    db_number: Optional[int] = 15


class DeviceHeartbeatRequest(BaseModel):
    name: str
    status: DeviceStatus = DeviceStatus.ONLINE


class DeviceResponse(BaseModel):
    id: int
    device_name: str
    device_type: str
    ip_address: str
    port: int = 8090
    simulator_mode: bool = False
    rack: int = 0
    slot: int = 1
    db_number: int = 15
    status: str
    error_code: Optional[str] = None
    last_heartbeat: datetime
    created_at: datetime


class DeviceConfigUpdateRequest(BaseModel):
    ip_address: Optional[str] = None
    port: Optional[int] = None
    simulator_mode: Optional[bool] = None
    rack: Optional[int] = None
    slot: Optional[int] = None
    db_number: Optional[int] = None


class DeviceTestConnectionRequest(BaseModel):
    device_name: str
    ip_address: Optional[str] = None
    port: Optional[int] = None
    payload: Optional[str] = "STATUS"
    timeout: Optional[float] = 3.0


class DeviceTestConnectionResponse(BaseModel):
    device_name: str
    success: bool
    ip_address: str
    port: int
    latency_ms: float = 0.0
    response_text: str = ""
    message: str = ""


class RawSocketCommandRequest(BaseModel):
    device_name: str
    command_text: str  # e.g. "MOVE_HOME", "PICK A1", "STORE B2", "STATUS", "LOCK_DRONE"
    target: Optional[str] = None
    timeout: Optional[float] = 10.0


class GenericDeviceCommandRequest(BaseModel):
    command: str
    target: Optional[str] = None


class DeviceCommandResponse(BaseModel):
    device: str
    command: str
    target: Optional[str] = None
    status: str = "DONE"
    message: str = ""


class DeviceCommandLogResponse(BaseModel):
    id: int
    device: str
    command: str
    target: Optional[str] = None
    timestamp: datetime
    result: str
    message: str




class PLCCommand(str, Enum):
    LOCK_DRONE = "LOCK_DRONE"
    UNLOCK_DRONE = "UNLOCK_DRONE"
    Z_UP = "Z_UP"
    Z_DOWN = "Z_DOWN"
    STOP_PLC = "STOP_PLC"
    START_PLC = "START_PLC"
    RESET_PLC = "RESET_PLC"
    # Staff Mode & Conveyor Commands (DB15 Byte 1)
    STAFF_MODE_ENABLE = "STAFF_MODE_ENABLE"
    STAFF_MODE_DISABLE = "STAFF_MODE_DISABLE"
    STAFF_OUTBOUND_START = "STAFF_OUTBOUND_START"
    STAFF_OUTBOUND_CANCEL = "STAFF_OUTBOUND_CANCEL"
    STAFF_INBOUND_START = "STAFF_INBOUND_START"
    STAFF_INBOUND_STOP = "STAFF_INBOUND_STOP"


class PLCCommandRequest(BaseModel):
    command: PLCCommand


class PLCStatusResponse(BaseModel):
    drone_detected: bool = False       # DB15.DBX2.0
    plc_locked_state: bool = False     # DB15.DBX2.1
    drone_locked: bool = False         # Alias for plc_locked_state
    plc_on: bool = False               # DB15.DBX2.4
    plc_error: bool = False            # DB15.DBX2.5
    emergency_stop: bool = False       # DB15.DBX2.6
    z_axis: str = "HOME"               # "HOME", "HÀNG A", "HÀNG B", "DRONE N1", "BĂNG TẢI O1", "MOVING"
    connected: bool = True
    simulator_mode: bool = True
    plc_busy: bool = False
    watchdog_active: bool = False      # True when DB15.DBX0.7 heartbeat task is running

    # Staff Mode & Conveyor Status (DB15 Byte 3 & Words 4, 6)
    sensor_conveyor_head: bool = False # DB15.DBX3.0 (Cảm biến đầu băng tải / O1)
    sensor_conveyor_end: bool = False  # DB15.DBX3.1 (Cảm biến cuối băng tải / Nhân viên)
    conveyor_running: bool = False     # DB15.DBX3.2 (Băng tải đang chạy)
    staff_outbound_busy: bool = False  # DB15.DBX3.3 (PLC đang xuất hàng)
    staff_outbound_done: bool = False  # DB15.DBX3.4 (PLC đã xuất xong danh sách)
    staff_inbound_busy: bool = False   # DB15.DBX3.5 (PLC đang nhận hàng)
    staff_inbound_done: bool = False   # DB15.DBX3.6 (PLC kết thúc nhận hàng)
    staff_mode_active: bool = False    # DB15.DBX3.7 (Xác nhận PLC ở Chế độ Nhân viên)
    staff_target_count: int = 0        # DB15.DBW4 (Số lượng hàng Backend yêu cầu PLC)
    staff_current_count: int = 0       # DB15.DBW6 (Số lượng hàng PLC đã đếm được)

    # Z-Axis Multi-Level Control (DB15.DBW8 + DB15.DBX2.7 + DB15.DBX0.2)
    cmd_target_z: bool = False         # DB15.DBX0.2 (Lệnh kích hoạt chạy trục Z đến tầng DBW8)
    plc_z_in_position: bool = False    # DB15.DBX2.7 (Z đã đến tầng mục tiêu, sẵn sàng)
    target_z_level: int = 0            # DB15.DBW8 (Mã tầng Z Backend yêu cầu)
    current_z_level: int = 0           # Mã tầng Z hiện tại PLC phản hồi



class RobotCommand(str, Enum):
    MOVE_HOME = "MOVE_HOME"
    STANDBY = "STANDBY"
    PICK_PRODUCT = "PICK_PRODUCT"
    PLACE_PRODUCT = "PLACE_PRODUCT"
    PICK = "PICK"
    STORE = "STORE"
    PICK_UAV = "PICK_UAV"
    PLACE_UAV = "PLACE_UAV"
    SCAN_QR_POS = "SCAN_QR_POS"
    OPEN_GRIPPER = "OPEN_GRIPPER"
    CLOSE_GRIPPER = "CLOSE_GRIPPER"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_upper = value.upper().strip()
            aliases = {
                "HOME": cls.MOVE_HOME,
                "MOVE_HOME": cls.MOVE_HOME,
                "STANDBY": cls.STANDBY,
                "MOVE_STANDBY": cls.STANDBY,
                "OUTBOUND": cls.STORE,
                "OUTBOUND_CYCLE": cls.STORE,
                "INBOUND": cls.PICK,
                "INBOUND_CYCLE": cls.PICK,
                "SCAN_QR": cls.SCAN_QR_POS,
                "SCAN_QR_POS": cls.SCAN_QR_POS,
                "PICK_PAD": cls.PICK_UAV,
                "PLACE_PAD": cls.PLACE_UAV,
                "PLACE_CONVEYOR": cls.STORE,
                "PICK_CONVEYOR": cls.PICK,
                "REQUEST_Z_DOWN": cls.MOVE_HOME,
                "REQUEST_Z_UP": cls.MOVE_HOME,
            }
            if val_upper in aliases:
                return aliases[val_upper]
        return super()._missing_(value)


class RobotCommandRequest(BaseModel):
    command: RobotCommand
    slot: Optional[str] = None   # e.g. "B2"


class RobotStatusResponse(BaseModel):
    state: str = "OFFLINE"          # "IDLE", "READY", "MOVING", "PICKING", "PLACING", "ERROR", "OFFLINE"
    current_slot: Optional[str] = None
    holding_product: Optional[str] = None
    connected: bool = False
    simulator_mode: bool = False


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
    updated_time: Optional[datetime] = None


class StorageSlotUpdateRequest(BaseModel):
    status: StorageSlotStatus
    product_id: Optional[str] = None
    qr_code: Optional[str] = None


class QRScanPayload(BaseModel):
    camera_id: str = "CAM01"
    qr: str
    sender_name: Optional[str] = None
    address: Optional[str] = None
    product_id: Optional[str] = None
    time: datetime = Field(default_factory=datetime.utcnow)


class StationProcessStep(BaseModel):
    step: int
    device: str
    action: str
    target_slot: Optional[str] = None
    description: str = ""
    status: str = "waiting"   # "waiting", "in_progress", "completed", "failed"


class StationProcessStatus(BaseModel):
    station_id: str = "STATION_WH_001"
    status: str = "waiting"     # "pending", "in_progress", "completed", "failed"
    current_step: str = "waiting"
    steps: list[StationProcessStep] = Field(default_factory=list)


class UAVMissionStep(BaseModel):
    step: int
    action: str
    start_location: str = "HOME"
    target_altitude: Optional[float] = None
    target_location: Optional[dict] = None
    description: str = ""
    status: str = "waiting"   # "waiting", "in_progress", "completed", "failed"


class UAVMissionStatus(BaseModel):
    drone_id: str = "UAV01"
    status: str = "waiting"     # "pending", "in_progress", "completed", "failed"
    current_step: str = "waiting"
    steps: list[UAVMissionStep] = Field(default_factory=list)


class StationOperationType(str, Enum):
    LOAD_PRODUCT = "LOAD_PRODUCT"      # Export / Delivery flow: Slot -> Dock
    UNLOAD_PRODUCT = "UNLOAD_PRODUCT"  # Import / Pickup flow: Dock -> Slot


class StationOperationResponse(BaseModel):
    station_id: str = "STATION_WH_001"
    operation: str                      # "LOAD_PRODUCT" or "UNLOAD_PRODUCT"
    status: str                         # "IDLE", "RUNNING", "COMPLETED", "FAILED"
    current_action: str                 # e.g. "PLC_LOCK_DRONE", "ROBOT_PICK_SLOT"
    target_slot: Optional[str] = None
    product_id: Optional[str] = None
    message: str = ""


class IntralogisticsMissionType(str, Enum):
    DRONE_PICKUP = "DRONE_PICKUP"
    DRONE_DELIVERY = "DRONE_DELIVERY"


class IntralogisticsMissionCreate(BaseModel):
    drone_id: str = "UAV01"
    mission_type: Optional[str] = "DRONE_PICKUP"
    task: Optional[str] = "PICKUP"         # "PICKUP" or "DELIVERY"
    product_id: str
    target_slot: Optional[str] = None
    order_id: Optional[int] = None
    priority: Optional[int] = 0


class IntralogisticsMissionResponse(BaseModel):
    id: int
    order_id: Optional[int] = None
    mission_type: str
    drone_id: str
    product_id: str
    target_slot: Optional[str] = None
    status: str                         # "WAITING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"
    current_phase: str                  # "WAITING", "STATION_PROCESSING", "DRONE_EN_ROUTE", "COMPLETED"
    state: str                          # Alias for status
    priority: int = 0
    error_reason: Optional[str] = None
    step_details: str = ""
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime


class MissionQueueResponse(BaseModel):
    active_mission: Optional[IntralogisticsMissionResponse] = None
    waiting_queue: list[IntralogisticsMissionResponse] = Field(default_factory=list)
    total_waiting: int = 0
    total_completed: int = 0
    total_failed: int = 0




