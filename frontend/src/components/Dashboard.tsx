import { useState } from "react";
import type { MissionLocations } from "../types/drone";
import { useWebSocket } from "../hooks/useWebSocket";
import { MissionForm } from "./MissionForm";
import { TelemetryPanel } from "./TelemetryPanel";
import { ControlButtons } from "./ControlButtons";

const DEFAULT_LOCATIONS: MissionLocations = {
  home_lat: 21.0285,
  home_lon: 105.8542,
  pickup_lat: 21.0290,
  pickup_lon: 105.8550,
  drop_lat: 21.0275,
  drop_lon: 105.8530,
};

export function Dashboard() {
  const { connected, telemetry, droneOnline, lastError } = useWebSocket();
  const [locations, setLocations] = useState<MissionLocations>(DEFAULT_LOCATIONS);

  return (
    <div className="dashboard">
      <header className="header">
        <h1>Drone Delivery Control</h1>
        <div className="connection-badges">
          <span className={`badge ${connected ? "online" : "offline"}`}>
            WS: {connected ? "Connected" : "Disconnected"}
          </span>
          <span className={`badge ${droneOnline ? "online" : "offline"}`}>
            Drone: {droneOnline ? "Online" : "Offline"}
          </span>
        </div>
      </header>

      {lastError && <div className="error-banner">{lastError}</div>}

      <main className="main-grid">
        <MissionForm onChange={setLocations} />
        <TelemetryPanel telemetry={telemetry} droneOnline={droneOnline} />
        <ControlButtons
          locations={locations}
          telemetry={telemetry}
          droneOnline={droneOnline}
        />
      </main>

      <footer className="footer">
        <span>LAN Mode — 192.168.2.28:8000</span>
        <span>No Internet / No Cloud</span>
      </footer>
    </div>
  );
}
