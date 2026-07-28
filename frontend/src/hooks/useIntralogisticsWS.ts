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

export function useIntralogisticsWS() {
  const [connected, setConnected] = useState(false);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [plc, setPlc] = useState<PLCState | null>(null);
  const [robot, setRobot] = useState<RobotState | null>(null);
  const [storage, setStorage] = useState<StorageSlot[]>([]);
  const [activeMission, setActiveMission] = useState<IntralogisticsMission | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number | null>(null);

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
        setPlc({
          hatch_open: plcData.z_axis === "UP",
          drone_locked: plcData.drone_locked ?? false,
          drone_landed_sensor: plcData.drone_detected ?? false,
          emergency_stop: plcData.emergency_stop ?? false,
          auto_mode: true,
        });
      }
      if (robotRes && robotRes.ok) {
        const robotData = await robotRes.json();
        setRobot({
          status: robotData.state === "ERROR" ? "ERROR" : robotData.state === "MOVING" ? "BUSY" : "IDLE",
          auto_mode: true,
          current_task: robotData.state,
          joint_positions: [0, 0, 0, 0, 0, 0],
          cartesian_position: { x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0 },
        });
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
          if (msg.devices) {
            setDevices(msg.devices);
            if (msg.plc) setPlc(msg.plc);
            if (msg.robot) setRobot(msg.robot);
            if (msg.storage) setStorage(msg.storage);
            if (msg.active_mission !== undefined) setActiveMission(msg.active_mission);
          } else {
            fetchState();
          }
        } catch {
          // ignore
        }
      };

      ws.onerror = () => {
        setLastError("Lỗi kết nối WebSocket System (/ws/system)");
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectTimer.current = window.setTimeout(connect, 3000);
      };
    } catch (err) {
      setLastError(err instanceof Error ? err.message : "Cannot connect to System WS");
      reconnectTimer.current = window.setTimeout(connect, 3000);
    }
  }, [fetchState]);

  useEffect(() => {
    fetchState();
    connect();
    const interval = setInterval(fetchState, 10000);
    return () => {
      clearInterval(interval);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
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
