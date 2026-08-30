import type { MissionLocations } from "../types/drone";

const getHost = () => {
  if (typeof window !== "undefined" && window.location.hostname) {
    return window.location.hostname;
  }
  return "192.168.137.1";
};

const defaultHost = getHost();
const API_BASE = import.meta.env.VITE_API_URL ?? `http://${defaultHost}:8000`;
const WS_URL = import.meta.env.VITE_WS_URL ?? `ws://${defaultHost}:8000/ws/client`;
const DRONE_ID = import.meta.env.VITE_DRONE_ID ?? "drone-01";

export { API_BASE, WS_URL, DRONE_ID };

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

export async function adminDeleteDeliveryRequest(id: number): Promise<Response> {
  return fetch(`${API_BASE}/admin/delivery-requests/${id}`, {
    method: "DELETE",
  });
}

export async function adminCompleteDeliveryRequest(id: number): Promise<Response> {
  return fetch(`${API_BASE}/admin/delivery-requests/${id}/complete`, {
    method: "POST",
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

export async function startPlc(): Promise<Response> {
  return fetch(`${API_BASE}/api/plc/start`, { method: "POST" });
}

export async function stopPlc(): Promise<Response> {
  return fetch(`${API_BASE}/api/plc/stop`, { method: "POST" });
}

export async function resetPlc(): Promise<Response> {
  return fetch(`${API_BASE}/api/plc/reset`, { method: "POST" });
}

export async function executePlcCommand(command: string): Promise<Response> {
  return fetch(`${API_BASE}/api/plc/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  });
}

export async function setSimulatedDroneSensor(detected: boolean): Promise<Response> {
  return fetch(`${API_BASE}/api/plc/sensor/drone-detected`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ detected }),
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

export async function sendRobotDoneSignal(): Promise<Response> {
  return fetch(`${API_BASE}/api/robot/done`, { method: "POST" });
}

export async function getInventorySlots(): Promise<Response> {
  return fetch(`${API_BASE}/api/inventory/slots`);
}

export async function clearStorageSlot(slotId: number | string): Promise<Response> {
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

export async function pauseMission(): Promise<Response> {
  return fetch(`${API_BASE}/api/missions/pause`, { method: "POST" });
}

export async function resumeMission(): Promise<Response> {
  return fetch(`${API_BASE}/api/missions/resume`, { method: "POST" });
}

export async function overrideMissionQR(productId: string): Promise<Response> {
  return fetch(`${API_BASE}/api/missions/override-qr`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: productId }),
  });
}

export async function sendPlcCommand(command: string): Promise<Response> {
  return fetch(`${API_BASE}/api/device/plc/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  });
}

export async function sendRobotCommand(command: string, target?: string): Promise<Response> {
  return fetch(`${API_BASE}/api/device/robot/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, target: target || null }),
  });
}

export async function startDeviceCamera(): Promise<Response> {
  return fetch(`${API_BASE}/api/device/camera/start`, { method: "POST" });
}

export async function stopDeviceCamera(): Promise<Response> {
  return fetch(`${API_BASE}/api/device/camera/stop`, { method: "POST" });
}

export async function testDeviceCameraQr(qrCode?: string): Promise<Response> {
  return fetch(`${API_BASE}/api/device/camera/qr_scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qr_code: qrCode || "PROD-TEST-1001" }),
  });
}



export async function getActiveMission(): Promise<Response> {
  return fetch(`${API_BASE}/api/mission/active`);
}

export async function getStationStatus(): Promise<Response> {
  return fetch(`${API_BASE}/api/station/status`);
}

export async function triggerAutoStartMissions(): Promise<Response> {
  return fetch(`${API_BASE}/api/mission/auto-start`, { method: "POST" });
}

export async function getDeviceLogs(limit = 50): Promise<Response> {
  return fetch(`${API_BASE}/api/device/logs?limit=${limit}`);
}

export async function updateDeviceConfig(
  deviceName: string,
  config: {
    ip_address?: string;
    port?: number;
    simulator_mode?: boolean;
    rack?: number;
    slot?: number;
    db_number?: number;
  }
): Promise<Response> {
  return fetch(`${API_BASE}/api/device/config/${deviceName}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
}

export async function testDeviceConnection(
  deviceName: string,
  ipAddress?: string,
  port?: number,
  payload?: string
): Promise<Response> {
  return fetch(`${API_BASE}/api/device/test-connection`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      device_name: deviceName,
      ip_address: ipAddress,
      port: port,
      payload: payload || "STATUS",
    }),
  });
}

export async function sendRawDeviceCommand(
  deviceName: string,
  commandText: string,
  target?: string
): Promise<Response> {
  return fetch(`${API_BASE}/api/device/send-raw-command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      device_name: deviceName,
      command_text: commandText,
      target: target || null,
    }),
  });
}

/** Get current Mission Queue (Active mission + WAITING FIFO list). */
export async function getMissionQueue(): Promise<Response> {
  return fetch(`${API_BASE}/api/mission/queue`);
}

/** Cancel a WAITING mission in queue. */
export async function cancelMission(missionId: number | string): Promise<Response> {
  return fetch(`${API_BASE}/api/mission/${missionId}/cancel`, {
    method: "POST",
  });
}

/** Create a new Mission and add it to Queue. */
export async function createMission(data: {
  mission_type: "DRONE_PICKUP" | "DRONE_DELIVERY";
  product_id: string;
  drone_id?: string;
  target_slot?: string;
  order_id?: number;
  priority?: number;
}): Promise<Response> {
  return fetch(`${API_BASE}/api/mission/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

/** Get all UAV Fleet units status. */
export async function getFleetStatus(): Promise<Response> {
  return fetch(`${API_BASE}/api/fleet/status`);
}

/** Signal/Simulate that UAV has arrived & landed at Docking Pad N1. */
export async function signalDroneArrived(droneId: string): Promise<Response> {
  return fetch(`${API_BASE}/api/fleet/${droneId}/signal/arrive`, {
    method: "POST",
  });
}

/** Signal/Simulate that UAV has departed and returned to Home pad. */
export async function signalDroneDepartHome(droneId: string): Promise<Response> {
  return fetch(`${API_BASE}/api/fleet/${droneId}/signal/depart-home`, {
    method: "POST",
  });
}

/** Signal/Simulate that UAV has departed for Customer Delivery. */
export async function signalDroneDepartDelivery(droneId: string): Promise<Response> {
  return fetch(`${API_BASE}/api/fleet/${droneId}/signal/depart-delivery`, {
    method: "POST",
  });
}

/** Set flight mode for a UAV (AUTO or MANUAL). */
export async function setDroneFlightMode(droneId: string, mode: "AUTO" | "MANUAL"): Promise<Response> {
  return fetch(`${API_BASE}/api/fleet/${droneId}/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
}

/** Get current System Operation Mode (AUTO or MANUAL). */
export async function getSystemMode(): Promise<Response> {
  return fetch(`${API_BASE}/api/system/mode`);
}

/** Set System Operation Mode (AUTO or MANUAL). */
export async function setSystemMode(mode: "AUTO" | "MANUAL"): Promise<Response> {
  return fetch(`${API_BASE}/api/system/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
}

/** Start Camera Vision device stream. */
export async function startCameraDevice(): Promise<Response> {
  return fetch(`${API_BASE}/api/device/camera/start`, {
    method: "POST",
  });
}

/** Stop Camera Vision device stream. */
export async function stopCameraDevice(): Promise<Response> {
  return fetch(`${API_BASE}/api/device/camera/stop`, {
    method: "POST",
  });
}

/** Trigger manual Camera QR code scan test. */
export async function triggerCameraQrScan(qrCode: string = "PROD-TEST-1001"): Promise<Response> {
  return fetch(`${API_BASE}/api/device/camera/qr_scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qr_code: qrCode }),
  });
}

/** System Auto Start: Pre-flight diagnostics, homing & dispatch FIFO Queue. */
export async function startSystemAuto(): Promise<Response> {
  return fetch(`${API_BASE}/api/system/start-auto`, {
    method: "POST",
  });
}

/** Pause System Auto scheduler without exiting AUTO mode. */
export async function pauseSystemAuto(): Promise<Response> {
  return fetch(`${API_BASE}/api/system/pause-auto`, {
    method: "POST",
  });
}

/** Resume System Auto scheduler after error/inspection. */
export async function resumeSystemQueue(): Promise<Response> {
  return fetch(`${API_BASE}/api/system/resume-queue`, {
    method: "POST",
  });
}

/** Reset all order history and generate 10 new sample orders in FIFO queue. */
export async function resetSampleOrders(): Promise<Response> {
  return fetch(`${API_BASE}/api/orders/reset-sample-10`, {
    method: "POST",
  });
}

// =========================================================================
// STAFF OPERATIONS API
// =========================================================================

/** Get full status of staff operation and system mode. */
export async function getStaffStatus(): Promise<Response> {
  return fetch(`${API_BASE}/api/staff/status`);
}

/** Switch operation mode (STATION_AUTO vs STAFF_OPERATION). */
export async function setStaffOperationMode(operationMode: "STATION_AUTO" | "STAFF_OPERATION"): Promise<Response> {
  return fetch(`${API_BASE}/api/staff/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operation_mode: operationMode }),
  });
}

/** Start Outbound picking flow for selected storage slots or target quantity. */
export async function startStaffOutbound(slots?: string[], quantity?: number): Promise<Response> {
  return fetch(`${API_BASE}/api/staff/outbound/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slots, quantity }),
  });
}

/** Cancel running Outbound picking flow. */
export async function cancelStaffOutbound(): Promise<Response> {
  return fetch(`${API_BASE}/api/staff/outbound/cancel`, {
    method: "POST",
  });
}

/** Start continuous Inbound storing flow from O1 to storage slots. */
export async function startStaffInbound(): Promise<Response> {
  return fetch(`${API_BASE}/api/staff/inbound/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
}

/** Stop running Inbound storing flow. */
export async function stopStaffInbound(): Promise<Response> {
  return fetch(`${API_BASE}/api/staff/inbound/stop`, {
    method: "POST",
  });
}












