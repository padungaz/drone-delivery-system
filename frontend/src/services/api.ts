import type { MissionLocations } from "../types/drone";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://192.168.2.28:8000";
const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://192.168.2.28:8000/ws/client";
const DRONE_ID = import.meta.env.VITE_DRONE_ID ?? "drone-01";

export { API_BASE, WS_URL, DRONE_ID };

/** Start a new delivery mission (also accepted during RETURN_HOME for Continuous Delivery). */
export async function startMission(locations: MissionLocations): Promise<Response> {
  return fetch(`${API_BASE}/missions/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...locations, action: "START", drone_id: DRONE_ID }),
  });
}

/** Operator confirms package has been picked up at the pickup location. */
export async function pickupComplete(locations: MissionLocations): Promise<Response> {
  return fetch(`${API_BASE}/missions/pickup-complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...locations, action: "PICKUP_COMPLETE", drone_id: DRONE_ID }),
  });
}

/** Operator confirms package has been delivered at the drop location. */
export async function dropComplete(locations: MissionLocations): Promise<Response> {
  return fetch(`${API_BASE}/missions/drop-complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...locations, action: "DROP_COMPLETE", drone_id: DRONE_ID }),
  });
}

/** Emergency: force the drone to return home immediately. */
export async function forceRtl(locations: MissionLocations): Promise<Response> {
  return fetch(`${API_BASE}/missions/force-rtl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...locations, action: "FORCE_RTL", drone_id: DRONE_ID }),
  });
}

/** Stop mission and reset to IDLE (only when landed + disarmed). */
export async function stopMission(locations: MissionLocations): Promise<Response> {
  return fetch(`${API_BASE}/missions/stop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...locations, action: "STOP", drone_id: DRONE_ID }),
  });
}

export async function getDroneStatus(): Promise<Response> {
  return fetch(`${API_BASE}/drones/${DRONE_ID}/status`);
}
