import { useState, useEffect, useRef, useCallback } from "react";
import type {
  DeviceInfo,
  PLCState,
  RobotState,
  StorageSlot,
  IntralogisticsMission,
} from "../types/drone";
import {
  SYSTEM_WS_URL,
  getDevices,
  getPlcStatus,
  getRobotStatus,
  getInventorySlots,
} from "../services/api";

/** Convert raw backend PLCStatusResponse to frontend PLCState with derived fields */
function mapPlcResponse(raw: Record<string, unknown>): PLCState {
  return {
    // Native backend fields (Handshake Protocol)
    drone_detected: (raw.drone_detected as boolean) ?? false,
    drone_locked: (raw.drone_locked as boolean) ?? false,
    z_axis: (raw.z_axis as string) ?? "HOME",
    emergency_stop: (raw.emergency_stop as boolean) ?? false,
    connected: (raw.connected as boolean) ?? true,
    simulator_mode: (raw.simulator_mode as boolean) ?? true,
    plc_busy: (raw.plc_busy as boolean) ?? false,
    plc_error: (raw.plc_error as boolean) ?? false,
    // Derived convenience fields
    hatch_open: (raw.z_axis as string) === "UP",
    drone_landed_sensor: (raw.drone_detected as boolean) ?? false,
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
  const [lastError, setLastError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const fetchState = useCallback(async () => {
    try {
      const [devRes, plcRes, robotRes, storageRes] = await Promise.all([
        getDevices().catch(() => null),
        getPlcStatus().catch(() => null),
        getRobotStatus().catch(() => null),
        getInventorySlots().catch(() => null),
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
              case "DEVICE_STATUS":
              case "DEVICE_HEARTBEAT":
              case "DEVICE_TIMEOUT":
                // Re-fetch device list for full consistency
                getDevices().then(async (res) => {
                  if (res.ok) setDevices(await res.json());
                }).catch(() => {});
                break;
              case "INVENTORY_STATUS":
                getInventorySlots().then(async (res) => {
                  if (res.ok) setStorage(await res.json());
                }).catch(() => {});
                break;
              case "MISSION_PROGRESS":
                if (msg.data.mission) {
                  setActiveMission(msg.data.mission);
                } else {
                  // Partial update — refresh from API
                  fetchState();
                }
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
    const interval = setInterval(fetchState, 10000);
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
  };
}
