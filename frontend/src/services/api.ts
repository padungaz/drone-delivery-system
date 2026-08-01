import type { MissionLocations } from "../types/drone";

const getHost = () => {
  if (typeof window !== "undefined" && window.location.hostname) {
    return window.location.hostname;
  }
  return "192.168.58.66";
};

const defaultHost = getHost();
const API_BASE = import.meta.env.VITE_API_URL ?? `http://${defaultHost}:8000`;
const WS_URL = import.meta.env.VITE_WS_URL ?? `ws://${defaultHost}:8000/ws/client`;
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

/** Send individual step command (Step-by-Step Flight Pipeline). */
export async function sendStepCommand(
  step_action: string,
  params?: { lat?: number; lon?: number; alt?: number }
): Promise<Response> {
  return fetch(`${API_BASE}/missions/step-command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      step_action,
      lat: params?.lat,
      lon: params?.lon,
      alt: params?.alt,
      drone_id: DRONE_ID,
    }),
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

// ---------------------------------------------------------------------------
// Smart Intralogistics System APIs
// ---------------------------------------------------------------------------

export const SYSTEM_WS_URL = import.meta.env.VITE_SYSTEM_WS_URL ?? API_BASE.replace(/^http/, "ws") + "/ws/system";

export async function getDevices(): Promise<Response> {
  return fetch(`${API_BASE}/api/device/list`);
}

export async function getPlcStatus(): Promise<Response> {
  return fetch(`${API_BASE}/api/plc/status`);
}

export async function controlPlcHatch(open: boolean): Promise<Response> {
  return fetch(`${API_BASE}/api/plc/hatch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: open ? "OPEN" : "CLOSE" }),
  });
}

export async function controlPlcLock(lock: boolean): Promise<Response> {
  return fetch(`${API_BASE}/api/plc/lock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: lock ? "LOCK" : "UNLOCK" }),
  });
}

export async function getRobotStatus(): Promise<Response> {
  return fetch(`${API_BASE}/api/robot/status`);
}

export async function executeRobotPick(targetSlot: string): Promise<Response> {
  return fetch(`${API_BASE}/api/robot/pick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: "DOCKING", target_slot: targetSlot }),
  });
}

export async function executeRobotPlace(sourceSlot: string): Promise<Response> {
  return fetch(`${API_BASE}/api/robot/place`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_slot: sourceSlot, target: "DOCKING" }),
  });
}

export async function robotEmergencyStop(): Promise<Response> {
  return fetch(`${API_BASE}/api/robot/emergency-stop`, { method: "POST" });
}

export async function getInventorySlots(): Promise<Response> {
  return fetch(`${API_BASE}/api/inventory/slots`);
}

export async function clearStorageSlot(slotId: number): Promise<Response> {
  return fetch(`${API_BASE}/api/inventory/slots/${slotId}/clear`, { method: "POST" });
}

export async function scanQR(qr: string): Promise<Response> {
  return fetch(`${API_BASE}/api/inventory/scan-qr`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qr }),
  });
}

export async function getIntralogisticsMissions(): Promise<Response> {
  return fetch(`${API_BASE}/api/missions`);
}

export async function startIntralogisticsMission(
  missionType: "DRONE_PICKUP" | "DRONE_DELIVERY",
  productId: string,
  targetSlot?: string,
): Promise<Response> {
  return fetch(`${API_BASE}/api/missions/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mission_type: missionType,
      drone_id: DRONE_ID,
      product_id: productId,
      target_slot: targetSlot || null,
    }),
  });
}

export async function startBackendCamera(): Promise<Response> {
  return fetch(`${API_BASE}/api/inventory/camera-scan/start`, { method: "POST" });
}

export async function stopBackendCamera(): Promise<Response> {
  return fetch(`${API_BASE}/api/inventory/camera-scan/stop`, { method: "POST" });
}

export async function getBackendCameraStatus(): Promise<Response> {
  return fetch(`${API_BASE}/api/inventory/camera-scan/status`);
}


