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

/** Send CAMERA_START command to drone via backend. */
export async function startCamera(): Promise<Response> {
  return fetch(`${API_BASE}/camera/start?drone_id=${DRONE_ID}`, {
    method: "POST",
  });
}

/** Send CAMERA_STOP command to drone via backend. */
export async function stopCamera(): Promise<Response> {
  return fetch(`${API_BASE}/camera/stop?drone_id=${DRONE_ID}`, {
    method: "POST",
  });
}

/** Set flight mode manually. */
export async function setFlightMode(mode: string): Promise<Response> {
  return fetch(`${API_BASE}/missions/set-mode?mode=${mode}&drone_id=${DRONE_ID}`, {
    method: "POST",
  });
}

/** Move drone relatively. */
export async function moveRelative(dx: number, dy: number, dz: number): Promise<Response> {
  return fetch(`${API_BASE}/missions/move-relative?dx=${dx}&dy=${dy}&dz=${dz}&drone_id=${DRONE_ID}`, {
    method: "POST",
  });
}

/** Manually ARM the drone (only when IDLE and disarmed). */
export async function armDrone(): Promise<Response> {
  return fetch(`${API_BASE}/missions/arm?drone_id=${DRONE_ID}`, {
    method: "POST",
  });
}

/** Manually DISARM the drone. Pass force=true to force-disarm even when flying (emergency). */
export async function disarmDrone(force = false): Promise<Response> {
  return fetch(`${API_BASE}/missions/disarm?force=${force}&drone_id=${DRONE_ID}`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Admin — Delivery Requests
// ---------------------------------------------------------------------------

export async function adminGetDeliveryRequests(status?: string): Promise<Response> {
  const params = status ? `?status=${status}` : "";
  return fetch(`${API_BASE}/admin/delivery-requests${params}`);
}

export async function adminGetDeliveryRequest(id: number): Promise<Response> {
  return fetch(`${API_BASE}/admin/delivery-requests/${id}`);
}

export async function adminUpdateDeliveryStatus(
  id: number,
  status: string,
  note?: string,
  missionId?: number,
): Promise<Response> {
  const params = new URLSearchParams({ status });
  if (note) params.append("note", note);
  if (missionId != null) params.append("mission_id", String(missionId));
  return fetch(`${API_BASE}/admin/delivery-requests/${id}/status?${params}`, {
    method: "PATCH",
  });
}

// ---------------------------------------------------------------------------
// Admin — Warehouse Config
// ---------------------------------------------------------------------------

export async function adminGetWarehouse(): Promise<Response> {
  return fetch(`${API_BASE}/admin/warehouse`);
}

export async function adminUpdateWarehouse(data: {
  name?: string;
  latitude?: number;
  longitude?: number;
  address_text?: string;
}): Promise<Response> {
  return fetch(`${API_BASE}/admin/warehouse`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Public — Warehouse (used by customer frontend too)
// ---------------------------------------------------------------------------

export async function getWarehouse(): Promise<Response> {
  return fetch(`${API_BASE}/warehouse`);
}

