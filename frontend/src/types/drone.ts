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
  armed: boolean;
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
