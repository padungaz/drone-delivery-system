import { useState, useEffect, useRef, useCallback } from "react";
import type { SystemBroadcastPayload } from "../types/drone";
import { SYSTEM_WS_URL } from "../services/api";

export function useIntralogisticsWS() {
  const [connected, setConnected] = useState(false);
  const [systemState, setSystemState] = useState<SystemBroadcastPayload | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number | null>(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(SYSTEM_WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setLastError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data: SystemBroadcastPayload = JSON.parse(event.data);
          setSystemState(data);
        } catch {
          // ignore non-json
        }
      };

      ws.onerror = () => {
        setLastError("Lỗi kết nối WebSocket System (/ws/system)");
      };

      ws.onclose = () => {
        setConnected(false);
        // Retry connection every 3s
        reconnectTimer.current = window.setTimeout(connect, 3000);
      };
    } catch (err) {
      setLastError(err instanceof Error ? err.message : "Cannot connect to System WS");
      reconnectTimer.current = window.setTimeout(connect, 3000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return {
    connected,
    systemState,
    lastError,
    devices: systemState?.devices ?? [],
    plc: systemState?.plc ?? null,
    robot: systemState?.robot ?? null,
    storage: systemState?.storage ?? [],
    activeMission: systemState?.active_mission ?? null,
  };
}
