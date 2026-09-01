import { useState, useEffect, useRef, useCallback } from "react";
import type {
  DeviceInfo,
  PLCState,
  RobotState,
  StorageSlot,
  IntralogisticsMission,
  StationOperation,
} from "../types/drone";
import {
  SYSTEM_WS_URL,
  getDevices,
  getPlcStatus,
  getRobotStatus,
  getInventorySlots,
  getActiveMission,
  getStationStatus,
} from "../services/api";

/** Convert raw backend PLCStatusResponse to frontend PLCState with derived fields */
function mapPlcResponse(raw: Record<string, unknown>): PLCState {
  const droneDetected = (raw.drone_detected as boolean) ?? false;
  const lockedState = (raw.plc_locked_state as boolean) ?? (raw.drone_locked as boolean) ?? false;
  const zAxis = (raw.z_axis as string) ?? "HOME";
  const currentZLevel = (raw.current_z_level as number) ?? 0;

  return {
    drone_detected: droneDetected,
    plc_locked_state: lockedState,
    drone_locked: lockedState,
    plc_on: (raw.plc_on as boolean) ?? true,
    plc_error: (raw.plc_error as boolean) ?? false,
    emergency_stop: (raw.emergency_stop as boolean) ?? false,
    z_axis: zAxis,
    connected: (raw.connected as boolean) ?? true,
    simulator_mode: (raw.simulator_mode as boolean) ?? true,
    plc_busy: (raw.plc_busy as boolean) ?? false,

    // Z-Axis Multi-Level Control
    cmd_target_z: (raw.cmd_target_z as boolean) ?? false,
    plc_z_in_position: (raw.plc_z_in_position as boolean) ?? true,
    target_z_level: (raw.target_z_level as number) ?? 0,
    current_z_level: currentZLevel,

    // Derived convenience fields
    hatch_open: currentZLevel === 3,
    drone_landed_sensor: droneDetected,
  };
}

/** Convert raw backend RobotStatusResponse to frontend RobotState */
function mapRobotResponse(raw: Record<string, unknown>): RobotState {
  const state = (raw.state as string) ?? "OFFLINE";
  const statusVal = state === "OFFLINE" ? "OFFLINE" : state === "ERROR" ? "ERROR" : state === "MOVING" || state === "PICKING" || state === "PLACING" ? "BUSY" : "IDLE";
  return {
    status: statusVal,
    auto_mode: true,
    current_task: state,
    joint_positions: (raw.joint_positions as number[]) ?? [0, 0, 0, 0, 0, 0],
    cartesian_position: (raw.cartesian_position as RobotState["cartesian_position"]) ?? { x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0 },
    connected: (raw.connected as boolean) ?? false,
    simulator_mode: (raw.simulator_mode as boolean) ?? false,
  };
}

export function useIntralogisticsWS() {
  const [connected, setConnected] = useState(false);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [plc, setPlc] = useState<PLCState | null>(null);
  const [robot, setRobot] = useState<RobotState | null>(null);
  const [storage, setStorage] = useState<StorageSlot[]>([]);
  const [activeMission, setActiveMission] = useState<IntralogisticsMission | null>(null);
  const [stationOp, setStationOp] = useState<StationOperation | null>(null);
  const [cameraActive, setCameraActive] = useState<boolean>(false);
  const [lastError, setLastError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const fetchState = useCallback(async () => {
    try {
      const [devRes, plcRes, robotRes, storageRes, missionRes, stationRes] = await Promise.all([
        getDevices().catch(() => null),
        getPlcStatus().catch(() => null),
        getRobotStatus().catch(() => null),
        getInventorySlots().catch(() => null),
        getActiveMission().catch(() => null),
        getStationStatus().catch(() => null),
      ]);

      if (devRes && devRes.ok) {
        const devs = await devRes.json();
        setDevices(devs);
      }
      if (plcRes && plcRes.ok) {
        const plcData = await plcRes.json();
        setPlc(mapPlcResponse(plcData));
      }
      if (robotRes && robotRes.ok) {
        const robotData = await robotRes.json();
        setRobot(mapRobotResponse(robotData));
      }
      if (storageRes && storageRes.ok) {
        const slots = await storageRes.json();
        setStorage(slots);
      }
      if (missionRes && missionRes.ok) {
        const activeM = await missionRes.json();
        if (activeM) setActiveMission(activeM);
      }
      if (stationRes && stationRes.ok) {
        const stationData = await stationRes.json();
        if (stationData) setStationOp(stationData);
      }
    } catch {
      // ignore fetch errors
    }
  }, []);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(SYSTEM_WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setLastError(null);
        fetchState();
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          // Handle structured broadcast events: { type: "...", data: {...} }
          if (msg.type && msg.data) {
            switch (msg.type) {
              case "PLC_STATUS":
                setPlc(mapPlcResponse(msg.data));
                break;
              case "ROBOT_STATUS":
                setRobot(mapRobotResponse(msg.data));
                break;
              case "CAMERA_STATUS":
                setCameraActive(Boolean(msg.data.is_active));
                break;
              case "DEVICE_STATUS":
              case "DEVICE_HEARTBEAT":
              case "DEVICE_TIMEOUT":
              case "DEVICE_CONFIG_UPDATED":
                if (msg.data?.device_name) {
                  setDevices((prev) => {
                    const exists = prev.some((d) => d.device_name === msg.data.device_name);
                    if (!exists) {
                      return [
                        ...prev,
                        {
                          device_name: msg.data.device_name,
                          device_type: msg.data.device_type || "DEVICE",
                          ip_address: msg.data.ip || msg.data.ip_address || "0.0.0.0",
                          port: msg.data.port || 0,
                          status: msg.data.status || "ONLINE",
                          last_heartbeat: new Date().toISOString(),
                          simulator_mode: msg.data.simulator_mode ?? false,
                        },
                      ];
                    }
                    return prev.map((d) =>
                      d.device_name === msg.data.device_name
                        ? {
                            ...d,
                            status: msg.data.status || d.status,
                            ip_address: msg.data.ip || msg.data.ip_address || d.ip_address,
                            port: msg.data.port !== undefined ? msg.data.port : d.port,
                            simulator_mode: msg.data.simulator_mode !== undefined ? msg.data.simulator_mode : d.simulator_mode,
                            last_heartbeat: new Date().toISOString(),
                          }
                        : d
                    );
                  });
                }
                break;
              case "INVENTORY_STATUS":
              case "STORAGE_UPDATE":
                if (Array.isArray(msg.data)) {
                  setStorage(msg.data);
                } else if (msg.data && Array.isArray(msg.data.slots)) {
                  setStorage(msg.data.slots);
                } else if (msg.data && (msg.data.slot_name || msg.data.id)) {
                  setStorage((prev) =>
                    prev.map((s) =>
                      s.slot_name === msg.data.slot_name || s.id === msg.data.id
                        ? {
                            ...s,
                            status: msg.data.status || "EMPTY",
                            product_id: msg.data.product_id || null,
                            qr_code: msg.data.qr_code || null,
                            is_empty: msg.data.status === "EMPTY" || !msg.data.product_id,
                          }
                        : s
                    )
                  );
                }
                break;
              case "STATION_STATUS":
                setStationOp(msg.data as StationOperation);
                break;
              case "MISSION_PROGRESS":
                if (msg.data.mission) {
                  setActiveMission(msg.data.mission);
                } else {
                  // Partial update — refresh from API
                  fetchState();
                }
                break;
              case "FLEET_UPDATE":
                window.dispatchEvent(new CustomEvent("fleet_update", { detail: msg.data }));
                break;
              case "MISSION_QUEUE_UPDATE":
                window.dispatchEvent(new CustomEvent("mission_queue_update", { detail: msg.data }));
                break;
              case "MISSION_STARTED":
                window.dispatchEvent(new CustomEvent("mission_started", { detail: msg.data }));
                fetchState();
                break;
              case "MISSION_COMPLETED":
                window.dispatchEvent(new CustomEvent("mission_completed", { detail: msg.data }));
                fetchState();
                break;
              case "MISSION_FAILED":
                window.dispatchEvent(new CustomEvent("mission_failed", { detail: msg.data }));
                fetchState();
                break;
              case "SYSTEM_ALERT":
                window.dispatchEvent(new CustomEvent("system_alert", { detail: msg.data }));
                break;
              case "SYSTEM_MODE_UPDATE":
                window.dispatchEvent(new CustomEvent("system_mode_update", { detail: msg.data }));
                break;
              case "STAFF_OPERATION_UPDATE":
                window.dispatchEvent(new CustomEvent("staff_operation_update", { detail: msg.data }));
                break;
              default:
                // Unknown event type — ignore
                break;
            }
          }
          // Handle full-state broadcast (legacy format): { devices: [...], plc: {...}, ... }
          else if (msg.devices) {
            setDevices(msg.devices);
            if (msg.plc) setPlc(mapPlcResponse(msg.plc));
            if (msg.robot) setRobot(mapRobotResponse(msg.robot));
            if (msg.storage) setStorage(msg.storage);
            if (msg.active_mission !== undefined) setActiveMission(msg.active_mission);
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onerror = () => {
        setLastError("Lỗi kết nối WebSocket System (/ws/system)");
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectTimer.current = setTimeout(connect, 3000);
      };
    } catch (err) {
      setLastError(err instanceof Error ? err.message : "Cannot connect to System WS");
      reconnectTimer.current = setTimeout(connect, 3000);
    }
  }, [fetchState]);

  useEffect(() => {
    fetchState();
    connect();
    // Fallback sync every 60s if WebSocket misses any event
    const interval = setInterval(fetchState, 60000);
    return () => {
      clearInterval(interval);
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect, fetchState]);

  return {
    connected,
    systemState: null,
    lastError,
    devices,
    plc,
    robot,
    storage,
    activeMission,
    stationOp,
    cameraActive,
    refetch: fetchState,
  };
}
