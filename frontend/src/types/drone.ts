// Primary mission states (new FSM)
export type DroneState =
  | "IDLE"
  | "ARMING"
  | "TAKEOFF"
  | "FLY_TO_PICKUP"
  | "DESCEND"
  | "SEARCH_ARUCO"
  | "PRECISION_LANDING"
  | "WAIT_PICKUP_CONFIRM"   // Drone landed at pickup — operator must confirm
  | "FLY_TO_DROP"
  | "WAIT_DROP_CONFIRM"     // Drone landed at drop — operator must confirm
  | "RETURN_HOME"           // Returning to home, auto-land, auto-disarm → IDLE
  | "ERROR"
  // Legacy states (may appear from older telemetry)
  | "PICKUP"
  | "DROP_PACKAGE"
  | "RTL"
  | "LAND"
  | "DISARM"
  | "LANDING";

export interface MissionLocations {
  home_lat: number;
  home_lon: number;
  pickup_lat: number;
  pickup_lon: number;
  drop_lat: number;
  drop_lon: number;
}

export type LandingLocation = "WAREHOUSE_PAD" | "CUSTOMER_PICKUP" | "CUSTOMER_DROP" | "UNKNOWN";

export interface Telemetry {
  timestamp: string;
  drone_id: string;
  drone_state: DroneState;
  latitude: number;
  longitude: number;
  altitude_relative: number;
  altitude_agl: number;
  battery: number;
  ground_speed: number;
  heading: number;
  gps_satellite: number;
  flight_mode: string;
  aruco_detected: boolean;
  landing_status: string;
  landing_phase: string;  // "pickup" | "drop" | "rtl" | "none"
  landing_location?: LandingLocation;
  armed: boolean;
  roll?: number;
  pitch?: number;
  yaw?: number;
  rangefinder_valid?: boolean;
}

export interface DroneStatus {
  drone_id: string;
  connected: boolean;
  last_telemetry: Telemetry | null;
  can_stop: boolean;
}

export interface WsMessage {
  type: string;
  payload: Record<string, unknown>;
}

// Button enable/disable logic helpers
export const PICKUP_OK_ENABLED_STATES: ReadonlySet<DroneState> = new Set([
  "WAIT_PICKUP_CONFIRM",
]);

export const DROP_OK_ENABLED_STATES: ReadonlySet<DroneState> = new Set([
  "WAIT_DROP_CONFIRM",
]);

export const FLYING_STATES: ReadonlySet<DroneState> = new Set([
  "ARMING",
  "TAKEOFF",
  "FLY_TO_PICKUP",
  "DESCEND",
  "SEARCH_ARUCO",
  "PRECISION_LANDING",
  "FLY_TO_DROP",
  "RETURN_HOME",
  // Legacy
  "LANDING",
  "RTL",
]);

// Camera test feature
export type CameraStatus = "OFF" | "ON" | "ERROR";

export interface ArucoDetection {
  aruco_detected: boolean;
  marker_id?: number;
  center_x?: number;
  center_y?: number;
  offset_x?: number;
  offset_y?: number;
  image_width?: number;
  image_height?: number;
  timestamp?: string;
}

// ── Smart Intralogistics Types ──────────────────────────────────────────────

export type DeviceType = "UAV" | "PLC" | "ROBOT" | "CAMERA";
export type DeviceStatusType = "ONLINE" | "OFFLINE" | "BUSY" | "ERROR";

export interface DeviceInfo {
  device_name: string;
  device_type: DeviceType;
  ip_address: string;
  port?: number;
  simulator_mode?: boolean;
  rack?: number;
  slot?: number;
  db_number?: number;
  status: DeviceStatusType;
  last_heartbeat: string;
}

export interface PLCState {
  // DB15 Byte 2 Status Fields
  drone_detected: boolean;       // DB15.DBX2.0
  plc_locked_state: boolean;     // DB15.DBX2.1
  drone_locked: boolean;         // Alias for plc_locked_state
  plc_on: boolean;               // DB15.DBX2.4
  plc_error: boolean;            // DB15.DBX2.5
  emergency_stop: boolean;       // DB15.DBX2.6

  // System & Connection State
  z_axis: string;                // "HOME" | "HÀNG A" | "HÀNG B" | "DRONE N1" | "BĂNG TẢI O1" | "MOVING"
  connected: boolean;
  simulator_mode: boolean;
  plc_busy: boolean;

  // Z-Axis Multi-Level Control (DB15.DBW8 + DB15.DBX2.7 + DB15.DBX0.2)
  cmd_target_z?: boolean;        // DB15.DBX0.2 (Lệnh kích hoạt chạy trục Z)
  plc_z_in_position?: boolean;   // DB15.DBX2.7 (Z đã đến tầng mục tiêu)
  target_z_level?: number;       // DB15.DBW8 (Mã tầng mục tiêu 0..4)
  current_z_level?: number;      // DB15.DBW8 (Mã tầng hiện tại)

  // Staff Mode & Conveyor Commands & Status (DB15 Byte 1, Byte 3)
  cmd_staff_outbound_cancel?: boolean;  // DB15.DBX1.2 (Lệnh Hủy xuất hàng)
  cmd_staff_inbound_stop?: boolean;     // DB15.DBX1.4 (Lệnh Dừng nạp hàng)
  staff_mode_active?: boolean;          // DB15.DBX3.7 (Xác nhận PLC ở Chế độ Nhân viên)
  staff_outbound_busy?: boolean;        // DB15.DBX3.3 (PLC đang xuất hàng)
  staff_inbound_busy?: boolean;         // DB15.DBX3.5 (PLC đang nhận hàng)

  // Derived convenience fields
  hatch_open: boolean;
  drone_landed_sensor: boolean;
}

export interface RobotState {
  status: "IDLE" | "BUSY" | "ERROR" | "OFFLINE";
  auto_mode: boolean;
  current_task: string | null;
  joint_positions: number[];
  cartesian_position: {
    x: number;
    y: number;
    z: number;
    rx: number;
    ry: number;
    rz: number;
  };
  connected?: boolean;
  simulator_mode?: boolean;
  holding_product?: string | null;
  current_slot?: string | null;
}

export type StorageSlotStatus = "EMPTY" | "OCCUPIED" | "RESERVED";

export interface StorageSlot {
  id: number;
  slot_name: string;
  status: StorageSlotStatus;
  product_id?: string | null;
  qr_code?: string | null;
  updated_time?: string | null;
  // Legacy fields
  is_empty?: boolean;
  sender_name?: string | null;
  sender_address?: string | null;
}

export interface StationProcessStep {
  step: number;
  device: string;
  action: string;
  target_slot?: string | null;
  description: string;
  status: "waiting" | "in_progress" | "completed" | "failed";
}

export interface StationProcessStatus {
  station_id: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  current_step: string;
  steps: StationProcessStep[];
}

export interface UAVMissionStep {
  step: number;
  action: string;
  start_location?: string;
  target_altitude?: number;
  target_location?: { latitude: number; longitude: number; altitude: number };
  description: string;
  status: "waiting" | "in_progress" | "completed" | "failed";
}

export interface UAVMissionStatus {
  drone_id: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  current_step: string;
  steps: UAVMissionStep[];
}

export interface StationOperation {
  station_id: string;
  operation: string;           // "LOAD_PRODUCT" | "UNLOAD_PRODUCT" | "NONE"
  status: string;              // "IDLE" | "RUNNING" | "COMPLETED" | "FAILED"
  current_action: string;      // e.g. "PLC_LOCK_DRONE", "ROBOT_PICK_SLOT"
  target_slot?: string | null;
  product_id?: string | null;
  message: string;
}

export interface IntralogisticsMission {
  id: number;
  order_id?: number | null;
  mission_type: "DRONE_PICKUP" | "DRONE_DELIVERY";
  drone_id: string;
  product_id: string;
  target_slot: string;
  status: string;              // "QUEUED" | "RUNNING" | "PAUSED" | "COMPLETED" | "FAILED" | "CANCELLED"
  current_phase: string;       // "WAITING" | "STATION_PROCESSING" | "DRONE_EN_ROUTE" | "DELIVERING_CUSTOMER" | "RETURNING_HOME" | "COMPLETED"
  state: string;               // Alias for status
  step_details: string;
  station_process?: StationProcessStatus | null;
  uav_mission?: UAVMissionStatus | null;
  created_at: string;
  updated_at: string;
}

export interface SystemBroadcastPayload {
  timestamp: string;
  devices: DeviceInfo[];
  plc: PLCState;
  robot: RobotState;
  storage: StorageSlot[];
  active_mission: IntralogisticsMission | null;
}

export interface DeviceCommandLog {
  id: number;
  device: string;
  command: string;
  target?: string | null;
  timestamp: string;
  result: string;
  message: string;
}



