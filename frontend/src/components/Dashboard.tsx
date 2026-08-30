import { useState, useEffect } from "react";
import type { MissionLocations } from "../types/drone";
import { useWebSocket } from "../hooks/useWebSocket";
import { useIntralogisticsWS } from "../hooks/useIntralogisticsWS";
import { ControlButtons } from "./ControlButtons";
import { DeliveryRequestsPanel } from "./DeliveryRequestsPanel";
import { MissionForm } from "./MissionForm";
import { TelemetryPanel } from "./TelemetryPanel";
import { WarehouseConfigPanel } from "./WarehouseConfigPanel";
import { ManualControlModal } from "./ManualControlModal";
import { MapPanel } from "./MapPanel";
import { IntralogisticsPanel } from "./IntralogisticsPanel";
import { StaffPortal } from "./StaffPortal";

const DEFAULT_LOCATIONS: MissionLocations = {
  home_lat: 0,
  home_lon: 0,
  pickup_lat: 0,
  pickup_lon: 0,
  drop_lat: 0,
  drop_lon: 0,
};

type ActiveTab = "intralogistics" | "staff" | "dashboard" | "map" | "split";

export function Dashboard() {
  const { telemetry, droneOnline, lastError } =
    useWebSocket();

  const {
    connected: sysWsConnected,
    devices,
    plc,
    robot,
    storage,
    activeMission,
    stationOp,
    cameraActive,
  } = useIntralogisticsWS();

  const [isManualModalOpen, setManualModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>("intralogistics");

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
  const [selectedTarget, setSelectedTarget] = useState<{ lat: number; lon: number } | null>(null);

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

  // Live clock for GCS Header
  const [clockTime, setClockTime] = useState("");
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setClockTime(now.toLocaleTimeString("vi-VN", { hour12: false }));
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // Quick device status checks for header badges
  const plcDev = devices.find((d) => d.device_type === "PLC");
  const robotDev = devices.find((d) => d.device_type === "ROBOT");
  const isPlcOnline = plcDev?.status === "ONLINE" || Boolean(plc?.connected) || Boolean(plc?.simulator_mode);
  const isRobotOnline = robotDev?.status === "ONLINE" && (Boolean(robot?.connected) || Boolean(robot?.simulator_mode));

  return (
    <div className="dashboard">
      <header className="header">
        <div className="header-left">
          <div className="header-branding">
            <span className="brand-badge fpt">FPT POLYTECHNIC</span>
            <span className="brand-badge team">⚡ ALPHA TEAM</span>
          </div>
          <h1>🚁 Smart Intralogistics & Drone Delivery GCS</h1>
          
          {/* Tab Navigation Bar */}
          <nav className="tab-navigation">
            <button
              type="button"
              className={`tab-btn ${activeTab === "intralogistics" ? "active" : ""}`}
              onClick={() => setActiveTab("intralogistics")}
            >
              🏭 Kho thông minh
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === "staff" ? "active" : ""}`}
              onClick={() => setActiveTab("staff")}
            >
              👨‍💼 Nhân viên kho
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === "dashboard" ? "active" : ""}`}
              onClick={() => setActiveTab("dashboard")}
            >
              📊 Ground Control Station
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === "map" ? "active" : ""}`}
              onClick={() => setActiveTab("map")}
            >
              🗺️ Live Map GPS
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === "split" ? "active" : ""}`}
              onClick={() => setActiveTab("split")}
            >
              🧩 Chế độ Song song
            </button>
          </nav>
        </div>

        <div className="header-right">
          {clockTime && <div className="gcs-clock">{clockTime} ICT</div>}
          <div className="connection-badges">
            <span className={`badge ${sysWsConnected ? "online" : "offline"}`}>
              WS System: {sysWsConnected ? "Online" : "Offline"}
            </span>
            <span className={`badge ${droneOnline ? "online" : "offline"}`}>
              UAV: {droneOnline ? "Online" : "Offline"}
            </span>
            <span className={`badge ${isPlcOnline ? "online" : "offline"}`}>
              PLC: {isPlcOnline ? "Online" : "Offline"}
            </span>
            <span className={`badge ${isRobotOnline ? "online" : "offline"}`}>
              Robot: {isRobotOnline ? "Online" : "Offline"}
            </span>
          </div>
        </div>
      </header>

      {lastError && <div className="error-banner">{lastError}</div>}

      {/* Tab: Kho thông minh (Smart Intralogistics) */}
      {activeTab === "intralogistics" && (
        <div className="view-container">
          <IntralogisticsPanel
            devices={devices}
            plc={plc}
            robot={robot}
            storage={storage}
            activeMission={activeMission}
            stationOp={stationOp}
            cameraActive={cameraActive}
          />
        </div>
      )}

      {/* Tab: Nhân viên kho (Staff Portal) */}
      {activeTab === "staff" && (
        <div className="view-container">
          <StaffPortal storageSlots={storage} />
        </div>
      )}


      {/* Tab: Full Map View */}
      {activeTab === "map" && (
        <div className="view-container">
          <MapPanel
            telemetry={telemetry}
            locations={locations}
            droneOnline={droneOnline}
            selectedTarget={selectedTarget}
            onSelectTarget={setSelectedTarget}
          />
          <div style={{ marginTop: "1rem" }}>
            <ControlButtons
              locations={locations}
              telemetry={telemetry}
              droneOnline={droneOnline}
              onOpenManual={() => setManualModalOpen(true)}
            />
          </div>
        </div>
      )}

      {/* Tab: Split View (Side-by-Side Operations Mode) */}
      {activeTab === "split" && (
        <div className="view-container split-view-layout">
          {/* Left Column: Drone Flight Operations (Map + Telemetry + Controls) */}
          <div className="split-column left-col">
            <MapPanel
              telemetry={telemetry}
              locations={locations}
              droneOnline={droneOnline}
              selectedTarget={selectedTarget}
              onSelectTarget={setSelectedTarget}
            />
            <div style={{ marginTop: "1rem" }}>
              <TelemetryPanel telemetry={telemetry} droneOnline={droneOnline} />
            </div>
            <div style={{ marginTop: "1rem" }}>
              <ControlButtons
                locations={locations}
                telemetry={telemetry}
                droneOnline={droneOnline}
                onOpenManual={() => setManualModalOpen(true)}
              />
            </div>
          </div>

          {/* Right Column: Intralogistics Warehouse & Camera Vision */}
          <div className="split-column right-col">
            <IntralogisticsPanel
              devices={devices}
              plc={plc}
              robot={robot}
              storage={storage}
              activeMission={activeMission}
              stationOp={stationOp}
              cameraActive={cameraActive}
            />
            <div style={{ marginTop: "1rem" }}>
              <DeliveryRequestsPanel
                homeLat={warehouseLat}
                homeLon={warehouseLon}
                onLocationsSelected={handleDeliveryLocations}
              />
            </div>
          </div>
        </div>
      )}

      {/* Tab: Classic Dashboard View */}
      {activeTab === "dashboard" && (
        <div className="view-container">
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

          {/* Row 3: Delivery Requests */}
          <div style={{ marginTop: "1rem" }}>
            <DeliveryRequestsPanel
              homeLat={warehouseLat}
              homeLon={warehouseLon}
              onLocationsSelected={handleDeliveryLocations}
            />
          </div>
        </div>
      )}

      {/* Manual Control Modal */}
      <ManualControlModal
        isOpen={isManualModalOpen}
        onClose={() => setManualModalOpen(false)}
        droneStatus={telemetry}
        locations={locations}
      />

      <footer className="footer">
        <span>FPT POLYTECHNIC — ALPHA TEAM</span>
        <span>LAN Mode — Smart Intralogistics & Drone Delivery GCS v2.5</span>
      </footer>
    </div>
  );
}
