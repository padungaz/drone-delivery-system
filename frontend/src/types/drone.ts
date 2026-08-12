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
export const START_ENABLED_STATES: ReadonlySet<DroneState> = new Set([
  "IDLE",
  "RETURN_HOME",
]);

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
  status: DeviceStatusType;
  last_heartbeat: string;
}

export interface PLCState {
  // Backend native fields (from PLCStatusResponse — Handshake Protocol)
  drone_detected: boolean;
  drone_locked: boolean;
  z_axis: string;            // "HOME" | "UP" | "DOWN" | "MOVING"
  emergency_stop: boolean;
  connected: boolean;
  simulator_mode: boolean;
  plc_busy: boolean;
  plc_error: boolean;
  // Derived convenience fields (computed on frontend)
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

export interface IntralogisticsMission {
  id: number;
  mission_type: "DRONE_PICKUP" | "DRONE_DELIVERY";
  drone_id: string;
  product_id: string;
  target_slot: string;
  state: string;
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


