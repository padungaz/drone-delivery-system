import { useState, useEffect } from "react";
import type { MissionLocations } from "../types/drone";
import { useWebSocket } from "../hooks/useWebSocket";
import { CameraPanel } from "./CameraPanel";
import { ControlButtons } from "./ControlButtons";
import { DeliveryRequestsPanel } from "./DeliveryRequestsPanel";
import { MissionForm } from "./MissionForm";
import { TelemetryPanel } from "./TelemetryPanel";
import { WarehouseConfigPanel } from "./WarehouseConfigPanel";
import { ManualControlModal } from "./ManualControlModal";

const DEFAULT_LOCATIONS: MissionLocations = {
  home_lat: 0,
  home_lon: 0,
  pickup_lat: 0,
  pickup_lon: 0,
  drop_lat: 0,
  drop_lon: 0,
};

export function Dashboard() {
  const { connected, telemetry, droneOnline, lastError, cameraStatus, arucoDetection } =
    useWebSocket();

  const [isManualModalOpen, setManualModalOpen] = useState(false);

  const [locations, setLocations] = useState<MissionLocations>(() => {
    const saved = localStorage.getItem("drone_admin_locations");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        // ignore JSON parse error
      }
    }
    return DEFAULT_LOCATIONS;
  });

  useEffect(() => {
    localStorage.setItem("drone_admin_locations", JSON.stringify(locations));
  }, [locations]);
  // Warehouse home coordinates (loaded from DB via WarehouseConfigPanel)
  const [warehouseLat, setWarehouseLat] = useState(0);
  const [warehouseLon, setWarehouseLon] = useState(0);

  const handleWarehouseLoaded = (lat: number, lon: number) => {
    setWarehouseLat(lat);
    setWarehouseLon(lon);
    // Auto-set home = warehouse coordinates
    setLocations((prev) => ({ ...prev, home_lat: lat, home_lon: lon }));
  };

  // Called by DeliveryRequestsPanel when "Chọn & START" is pressed
  const handleDeliveryLocations = (loc: MissionLocations) => {
    setLocations(loc);
  };

  return (
    <div className="dashboard">
      <header className="header">
        <h1>🚁 Drone Delivery — Admin</h1>
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

      {/* Row 1: Warehouse + Telemetry */}
      <div className="main-grid">
        <WarehouseConfigPanel onWarehouseLoaded={handleWarehouseLoaded} />
        <TelemetryPanel telemetry={telemetry} droneOnline={droneOnline} />
      </div>

      {/* Row 2: Mission Form + Controls */}
      <div className="main-grid" style={{ marginTop: "1rem" }}>
        <MissionForm onChange={setLocations} initialLocations={locations} />
        <ControlButtons 
          locations={locations} 
          telemetry={telemetry} 
          droneOnline={droneOnline} 
          onOpenManual={() => setManualModalOpen(true)} 
        />
      </div>

      {/* Row 3: Camera */}
      <div style={{ marginTop: "1rem" }}>
        <CameraPanel
          cameraStatus={cameraStatus}
          arucoDetection={arucoDetection}
          droneOnline={droneOnline}
        />
      </div>

      {/* Row 4: Delivery Requests (full width) */}
      <div style={{ marginTop: "1rem" }}>
        <DeliveryRequestsPanel
          homeLat={warehouseLat}
          homeLon={warehouseLon}
          onLocationsSelected={handleDeliveryLocations}
        />
      </div>

      {/* Manual Control Modal */}
      <ManualControlModal 
        isOpen={isManualModalOpen} 
        onClose={() => setManualModalOpen(false)} 
        droneStatus={telemetry} 
      />

      <footer className="footer">
        <span>LAN Mode — Admin Dashboard</span>
        <span>Drone Delivery System v2.0</span>
      </footer>
    </div>
  );
}
