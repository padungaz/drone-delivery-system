import { useCallback, useEffect, useRef, useState } from "react";
import type { Telemetry, WsMessage } from "../types/drone";
import { WS_URL } from "../services/api";

const RECONNECT_DELAY_MS = 3000;

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [droneOnline, setDroneOnline] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setLastError(null);
    };

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        if (msg.type === "telemetry") {
          setTelemetry(msg.payload as unknown as Telemetry);
          setDroneOnline(true);
        } else if (msg.type === "drone_connected") {
          setDroneOnline(true);
        } else if (msg.type === "drone_disconnected") {
          setDroneOnline(false);
        } else if (msg.type === "error") {
          setLastError(String(msg.payload.message ?? "Unknown error"));
        }
      } catch {
        setLastError("Failed to parse WebSocket message");
      }
    };

    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    ws.onerror = () => {
      setLastError("WebSocket connection error");
      ws.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected, telemetry, droneOnline, lastError };
}
