import { useState, useEffect } from "react";
import {
  startUavSimFlight,
  pauseUavSimFlight,
  resumeUavSimFlight,
  rtlUavSimFlight,
  stopUavSimFlight,
  setUavSimFlightSpeed,
  getUavSimFlightStatus,
} from "../../services/api";
import type { MissionLocations } from "../../types/drone";

interface Props {
  locations: MissionLocations;
  onUpdateLocations?: (locations: MissionLocations) => void;
  selectedTarget?: { lat: number; lon: number } | null;
}

const SAMPLE_MISSIONS = [
  {
    id: 101,
    title: "Đơn #101: Giao Hàng Thuốc Y Tế (Hải Châu)",
    type: "DRONE_DELIVERY",
    product: "THUOC-CAP-CUU-01",
    target_lat: 16.0592,
    target_lon: 108.2085,
    distance_desc: "~850m từ Trạm N1",
  },
  {
    id: 102,
    title: "Đơn #102: Giao Kiện Hàng Hỏa Tốc (Sơn Trà)",
    type: "DRONE_DELIVERY",
    product: "LINH-KIEN-02",
    target_lat: 16.0650,
    target_lon: 108.2140,
    distance_desc: "~1.5km từ Trạm N1",
  },
  {
    id: 103,
    title: "Đơn #103: Nhận Hàng Hoàn Về Kho (Cẩm Lệ)",
    type: "DRONE_PICKUP",
    product: "HOAN-HANG-03",
    target_lat: 16.0460,
    target_lon: 108.2090,
    distance_desc: "~1.1km từ Trạm N1",
  },
];

export function UavMissionFlightWidget({
  locations,
  onUpdateLocations,
  selectedTarget,
}: Props) {
  const [selectedMissionId, setSelectedMissionId] = useState<number>(101);
  const [speedMultiplier, setSpeedMultiplier] = useState<number>(2.0);
  const [loading, setLoading] = useState(false);
  const [flightState, setFlightState] = useState<any>({
    is_running: false,
    is_paused: false,
    flight_phase: "IDLE",
    progress_percent: 0,
    current: { lat: 16.0544, lon: 108.2022, altitude: 0, speed: 0, heading: 0, battery: 98 },
    step_message: "Sẵn sàng bay mô phỏng theo nhiệm vụ.",
  });

  const activeMission = SAMPLE_MISSIONS.find((m) => m.id === selectedMissionId) || SAMPLE_MISSIONS[0];

  // Sync selected target if clicked on map
  useEffect(() => {
    if (selectedTarget && selectedTarget.lat && selectedTarget.lon) {
      if (onUpdateLocations) {
        onUpdateLocations({
          ...locations,
          drop_lat: selectedTarget.lat,
          drop_lon: selectedTarget.lon,
        });
      }
    }
  }, [selectedTarget]);

  // Listen to WebSocket flight updates
  useEffect(() => {
    const handleFlightUpdate = (e: any) => {
      if (e.detail) {
        setFlightState(e.detail);
      }
    };
    window.addEventListener("uav_mission_flight_update", handleFlightUpdate);

    // Initial status poll
    getUavSimFlightStatus()
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setFlightState(data);
      })
      .catch(() => null);

    return () => {
      window.removeEventListener("uav_mission_flight_update", handleFlightUpdate);
    };
  }, []);

  const handleStartFlight = async () => {
    setLoading(true);
    const targetLat = activeMission.target_lat;
    const targetLon = activeMission.target_lon;
    const homeLat = locations.home_lat || 16.0544;
    const homeLon = locations.home_lon || 108.2022;

    if (onUpdateLocations) {
      onUpdateLocations({
        ...locations,
        home_lat: homeLat,
        home_lon: homeLon,
        drop_lat: targetLat,
        drop_lon: targetLon,
      });
    }

    try {
      await startUavSimFlight({
        mission_id: activeMission.id,
        mission_type: activeMission.type,
        home_lat: homeLat,
        home_lon: homeLon,
        target_lat: targetLat,
        target_lon: targetLon,
        speed_multiplier: speedMultiplier,
      });
    } catch (err) {
      console.error("Failed to start sim flight:", err);
    } finally {
      setLoading(false);
    }
  };

  const handlePauseResume = async () => {
    try {
      if (flightState.is_paused) {
        await resumeUavSimFlight();
      } else {
        await pauseUavSimFlight();
      }
    } catch (err) {
      console.error("Pause/Resume failed:", err);
    }
  };

  const handleRtl = async () => {
    try {
      await rtlUavSimFlight();
    } catch (err) {
      console.error("RTL failed:", err);
    }
  };

  const handleStopFlight = async () => {
    try {
      await stopUavSimFlight();
    } catch (err) {
      console.error("Stop flight failed:", err);
    }
  };

  const handleSpeedChange = async (newSpeed: number) => {
    setSpeedMultiplier(newSpeed);
    try {
      await setUavSimFlightSpeed(newSpeed);
    } catch (err) {
      console.error("Set speed failed:", err);
    }
  };

  const isRunning = flightState?.is_running;
  const isPaused = flightState?.is_paused;
  const phase = flightState?.flight_phase || "IDLE";
  const progress = flightState?.progress_percent || 0;

  return (
    <div className="card-panel uav-sim-flight-widget" style={{ marginTop: "1rem" }}>
      <div className="card-header flex-between">
        <div className="card-title-group">
          <h3>🚁 BAY THEO NHIỆM VỤ (MÔ PHỎNG GPS)</h3>
          <span className="card-subtitle">AUTONOMOUS MISSION FLIGHT SIMULATION</span>
        </div>
        <div className={`status-pill ${isRunning ? "pill-running" : "pill-standby"}`} style={{
          padding: "4px 10px",
          borderRadius: "6px",
          fontSize: "0.75rem",
          fontWeight: 700,
          background: isRunning ? "rgba(16, 185, 129, 0.2)" : "rgba(100, 116, 139, 0.2)",
          color: isRunning ? "#34d399" : "#94a3b8",
          border: `1px solid ${isRunning ? "#10b981" : "rgba(255,255,255,0.1)"}`,
        }}>
          {isRunning ? (isPaused ? "⏸️ TẠM DỪNG" : `⚡ ${phase}`) : "READY (SẴN SÀNG)"}
        </div>
      </div>

      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "12px", padding: "14px" }}>
        {/* Mission Selector */}
        <div className="flight-selector-box" style={{ background: "rgba(15, 23, 42, 0.7)", padding: "10px", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.08)" }}>
          <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 700, color: "#94a3b8", marginBottom: "6px" }}>
            CHỌN NHIỆM VỤ HỆ THỐNG:
          </label>
          <select
            value={selectedMissionId}
            onChange={(e) => setSelectedMissionId(Number(e.target.value))}
            disabled={isRunning}
            style={{
              width: "100%",
              padding: "8px 10px",
              background: "#020617",
              border: "1px solid rgba(0, 240, 255, 0.4)",
              borderRadius: "6px",
              color: "#00f0ff",
              fontSize: "0.85rem",
              fontWeight: 600,
              outline: "none",
            }}
          >
            {SAMPLE_MISSIONS.map((m) => (
              <option key={m.id} value={m.id} style={{ background: "#0f172a", color: "#f8fafc" }}>
                {m.title} ({m.distance_desc})
              </option>
            ))}
          </select>
          <div style={{ marginTop: "6px", fontSize: "0.72rem", color: "#64748b", display: "flex", justifyContent: "space-between" }}>
            <span>Tọa độ đích: <b>{activeMission.target_lat.toFixed(4)}, {activeMission.target_lon.toFixed(4)}</b></span>
            <span>Loại: <b>{activeMission.type}</b></span>
          </div>
        </div>

        {/* Speed Multiplier Controls */}
        <div className="speed-selector-row" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(15, 23, 42, 0.7)", padding: "8px 12px", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.08)" }}>
          <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#cbd5e1" }}>TỐC ĐỘ MÔ PHỎNG:</span>
          <div style={{ display: "flex", gap: "6px" }}>
            {[1.0, 2.0, 5.0].map((spd) => (
              <button
                key={spd}
                type="button"
                onClick={() => handleSpeedChange(spd)}
                style={{
                  padding: "4px 10px",
                  borderRadius: "4px",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  cursor: "pointer",
                  border: speedMultiplier === spd ? "1px solid #00f0ff" : "1px solid rgba(255,255,255,0.15)",
                  background: speedMultiplier === spd ? "rgba(0, 240, 255, 0.2)" : "rgba(30, 41, 59, 0.6)",
                  color: speedMultiplier === spd ? "#00f0ff" : "#94a3b8",
                }}
              >
                {spd}x {spd === 1.0 ? "(Chuẩn)" : spd === 5.0 ? "(Siêu tốc)" : ""}
              </button>
            ))}
          </div>
        </div>

        {/* HUD Flight Progress & Telemetry */}
        <div className="flight-hud-box" style={{ background: "rgba(2, 6, 23, 0.9)", padding: "12px", borderRadius: "8px", border: "1px solid rgba(0, 240, 255, 0.2)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#38bdf8" }}>TIẾN TRÌNH CHUYẾN BAY:</span>
            <span style={{ fontSize: "0.85rem", fontWeight: 800, color: "#00f0ff" }}>{progress.toFixed(0)}%</span>
          </div>
          
          {/* Progress Bar */}
          <div style={{ width: "100%", height: "8px", background: "rgba(255,255,255,0.1)", borderRadius: "4px", overflow: "hidden", marginBottom: "10px" }}>
            <div style={{
              width: `${progress}%`,
              height: "100%",
              background: "linear-gradient(90deg, #0284c7 0%, #00f0ff 100%)",
              boxShadow: "0 0 8px rgba(0, 240, 255, 0.8)",
              transition: "width 0.4s ease",
            }} />
          </div>

          {/* Telemetry Metrics Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px", textAlign: "center" }}>
            <div style={{ background: "rgba(15, 23, 42, 0.8)", padding: "6px", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.05)" }}>
              <small style={{ display: "block", fontSize: "0.65rem", color: "#64748b" }}>ĐỘ CAO</small>
              <strong style={{ fontSize: "0.85rem", color: "#f8fafc" }}>{flightState?.current?.altitude || 0}m</strong>
            </div>
            <div style={{ background: "rgba(15, 23, 42, 0.8)", padding: "6px", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.05)" }}>
              <small style={{ display: "block", fontSize: "0.65rem", color: "#64748b" }}>VẬN TỐC</small>
              <strong style={{ fontSize: "0.85rem", color: "#38bdf8" }}>{flightState?.current?.speed || 0} m/s</strong>
            </div>
            <div style={{ background: "rgba(15, 23, 42, 0.8)", padding: "6px", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.05)" }}>
              <small style={{ display: "block", fontSize: "0.65rem", color: "#64748b" }}>PIN UAV</small>
              <strong style={{ fontSize: "0.85rem", color: "#34d399" }}>{flightState?.current?.battery || 98}%</strong>
            </div>
            <div style={{ background: "rgba(15, 23, 42, 0.8)", padding: "6px", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.05)" }}>
              <small style={{ display: "block", fontSize: "0.65rem", color: "#64748b" }}>HƯỚNG BAY</small>
              <strong style={{ fontSize: "0.85rem", color: "#fbbf24" }}>{flightState?.current?.heading || 0}°</strong>
            </div>
          </div>

          {/* Phase Message */}
          <div style={{ marginTop: "10px", padding: "6px 10px", borderRadius: "6px", background: "rgba(15, 23, 42, 0.9)", fontSize: "0.75rem", color: "#94a3b8", display: "flex", alignItems: "center", gap: "6px" }}>
            <span>📡</span>
            <span style={{ color: "#e2e8f0", fontWeight: 500 }}>{flightState?.step_message || "Chờ lệnh bay..."}</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: "grid", gridTemplateColumns: isRunning ? "1fr 1fr 1fr" : "1fr", gap: "8px" }}>
          {!isRunning ? (
            <button
              type="button"
              onClick={handleStartFlight}
              disabled={loading}
              style={{
                padding: "10px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)",
                border: "1px solid #38bdf8",
                color: "#ffffff",
                fontWeight: 700,
                fontSize: "0.85rem",
                cursor: "pointer",
                boxShadow: "0 0 12px rgba(56, 189, 248, 0.4)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
              }}
            >
              <span>▶️</span>
              <span>BẮT ĐẦU BAY THEO NHIỆM VỤ</span>
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={handlePauseResume}
                style={{
                  padding: "8px",
                  borderRadius: "6px",
                  background: isPaused ? "rgba(16, 185, 129, 0.2)" : "rgba(245, 158, 11, 0.2)",
                  border: isPaused ? "1px solid #10b981" : "1px solid #f59e0b",
                  color: isPaused ? "#34d399" : "#fbbf24",
                  fontWeight: 700,
                  fontSize: "0.75rem",
                  cursor: "pointer",
                }}
              >
                {isPaused ? "▶️ TIẾP TỤC" : "⏸️ TẠM DỪNG"}
              </button>

              <button
                type="button"
                onClick={handleRtl}
                style={{
                  padding: "8px",
                  borderRadius: "6px",
                  background: "rgba(56, 189, 248, 0.2)",
                  border: "1px solid #38bdf8",
                  color: "#38bdf8",
                  fontWeight: 700,
                  fontSize: "0.75rem",
                  cursor: "pointer",
                }}
              >
                🏠 VỀ TRẠM (RTL)
              </button>

              <button
                type="button"
                onClick={handleStopFlight}
                style={{
                  padding: "8px",
                  borderRadius: "6px",
                  background: "rgba(239, 68, 68, 0.2)",
                  border: "1px solid #ef4444",
                  color: "#f87171",
                  fontWeight: 700,
                  fontSize: "0.75rem",
                  cursor: "pointer",
                }}
              >
                ⏹️ HỦY BAY
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
