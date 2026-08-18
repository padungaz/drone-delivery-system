import { useState } from "react";
import {
  setFlightMode,
  startCamera,
  stopCamera,
  armDrone,
  disarmDrone,
  sendStepCommand,
} from "../../services/api";
import type { MissionLocations } from "../../types/drone";

interface Props {
  droneStatus?: any;
  locations?: MissionLocations;
  droneOnline?: boolean;
}

const FLIGHT_MODES = [
  { label: "🟡 Hold / Loiter", value: "LOITER", desc: "Giữ vị trí & bay tới đích (DO_REPOSITION)" },
  { label: "🛫 Takeoff", value: "TAKEOFF", desc: "Cất cánh tự động lên độ cao an toàn" },
  { label: "🛬 Land", value: "LAND", desc: "Hạ cánh tự động tại vị trí hiện tại" },
  { label: "🏠 Return (RTL)", value: "RTL", desc: "Bay quay về Trạm xuất phát và đáp" },
];

function isModeActive(modeValue: string, flightMode?: string, droneState?: string): boolean {
  const mode = (flightMode || "").toUpperCase();
  const state = (droneState || "").toUpperCase();

  switch (modeValue) {
    case "LOITER":
      return (
        mode.includes("LOITER") ||
        mode.includes("HOLD") ||
        mode.includes("POSCTL") ||
        mode.includes("MANUAL") ||
        state === "IDLE" ||
        state === "WAIT_PICKUP_CONFIRM" ||
        state === "WAIT_DROP_CONFIRM"
      );
    case "TAKEOFF":
      return mode.includes("TAKEOFF") || state === "TAKEOFF";
    case "LAND":
      return (
        mode.includes("LAND") ||
        mode.includes("PRECLAND") ||
        state === "DESCEND_SEARCH" ||
        state === "PRECISION_LANDING"
      );
    case "RTL":
      return mode.includes("RTL") || state === "RETURN_HOME";
    default:
      return mode === modeValue || state === modeValue;
  }
}

export function UavManualControlPanel({ droneStatus, locations, droneOnline = true }: Props) {
  const [armLoading, setArmLoading] = useState<string | null>(null);
  const [stepMsg, setStepMsg] = useState<string | null>(null);

  // GPS target choice for Step 3 (NAV_GPS)
  const [targetType, setTargetType] = useState<"home" | "pickup" | "drop" | "custom">("pickup");
  const [customLat, setCustomLat] = useState<number>(16.0544);
  const [customLon, setCustomLon] = useState<number>(108.2022);
  const [targetAlt, setTargetAlt] = useState<number>(1.5);

  const isArmed: boolean = droneStatus?.armed ?? false;
  const currentState: string = droneStatus?.drone_state || "IDLE";
  const flightMode: string = droneStatus?.flight_mode || "UNKNOWN";

  const handleStepAction = async (step_action: string, extraParams?: { lat?: number; lon?: number; alt?: number }) => {
    setArmLoading(step_action);
    setStepMsg(null);
    try {
      let params = extraParams;
      if (step_action === "NAV_GPS" && !params) {
        let lat = customLat;
        let lon = customLon;
        if (targetType === "home") {
          lat = locations?.home_lat || 16.0544;
          lon = locations?.home_lon || 108.2022;
        } else if (targetType === "pickup") {
          lat = locations?.pickup_lat || 16.0544;
          lon = locations?.pickup_lon || 108.2022;
        } else if (targetType === "drop") {
          lat = locations?.drop_lat || 16.0544;
          lon = locations?.drop_lon || 108.2022;
        }
        params = { lat, lon, alt: targetAlt };
      }

      const res = await sendStepCommand(step_action, params);
      const data = await res.json();
      if (res.ok) {
        setStepMsg(`✅ Bước [${step_action}]: Gửi thành công!`);
      } else {
        setStepMsg(`❌ Lỗi [${step_action}]: ${data.detail || "Không thể gửi lệnh"}`);
      }
    } catch (err) {
      console.error(`Failed to send step action ${step_action}`, err);
      setStepMsg(`❌ Lỗi kết nối mạng khi gửi [${step_action}]`);
    } finally {
      setArmLoading(null);
    }
  };

  const handleSetMode = async (mode: string) => {
    if ((mode === "LOITER" || mode === "TAKEOFF") && !isArmed) {
      setStepMsg(`⚠️ Vui lòng ARM trước khi chọn chế độ ${mode}`);
      return;
    }
    setStepMsg(null);
    try {
      const res = await setFlightMode(mode);
      const data = await res.json();
      setStepMsg(res.ok ? `✅ Đã chuyển sang chế độ ${mode}` : `❌ ${data.detail ?? "Lỗi đặt chế độ"}`);
    } catch (err) {
      console.error("Failed to set mode", err);
      setStepMsg("❌ Lỗi mạng khi đặt chế độ");
    }
  };

  const handleCamera = async (action: "start" | "stop") => {
    try {
      if (action === "start") await startCamera();
      else await stopCamera();
      setStepMsg(`✅ Camera: ${action.toUpperCase()}`);
    } catch (err) {
      console.error(`Failed to ${action} camera`, err);
      setStepMsg(`❌ Lỗi camera: ${action}`);
    }
  };

  const handleArm = async () => {
    setArmLoading("arm");
    setStepMsg(null);
    try {
      const res = await armDrone();
      const data = await res.json();
      setStepMsg(res.ok ? `✅ ${data.status}` : `❌ ${data.detail ?? "Khởi động ARM thất bại"}`);
    } catch {
      setStepMsg("❌ Lỗi mạng khi ARM");
    } finally {
      setArmLoading(null);
    }
  };

  const handleDisarm = async (force = false) => {
    if (force && !window.confirm("⚠️ Khẩn cấp: Tắt động cơ sẽ khiến Drone rơi tự do nếu đang bay. Bạn chắc chắn chứ?")) return;
    setArmLoading(force ? "force" : "disarm");
    setStepMsg(null);
    try {
      const res = await disarmDrone(force);
      const data = await res.json();
      setStepMsg(res.ok ? `✅ ${data.status}` : `❌ ${data.detail ?? "Tắt động cơ thất bại"}`);
    } catch {
      setStepMsg("❌ Lỗi mạng khi Disarm");
    } finally {
      setArmLoading(null);
    }
  };

  return (
    <div className="hmi-card uav-manual-control-card" style={{ display: "flex", flexDirection: "column", height: "100%", maxHeight: "560px" }}>
      {/* Card Header */}
      <div className="card-header flex-between" style={{ padding: "0.6rem 0.85rem", borderBottom: "1px solid rgba(0, 240, 255, 0.2)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "1.1rem" }}>🎮</span>
          <div>
            <h3 style={{ margin: 0, fontSize: "0.92rem", letterSpacing: "0.5px", color: "#00F0FF" }}>
              ĐIỀU KHIỂN & KIỂM THỬ UAV
            </h3>
            <span style={{ fontSize: "0.68rem", color: "#94a3b8" }}>Manual Flight & Step Pipeline</span>
          </div>
        </div>

        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <span
            style={{
              fontSize: "0.7rem",
              fontWeight: "bold",
              padding: "0.15rem 0.5rem",
              borderRadius: "4px",
              background: isArmed ? "rgba(239, 68, 68, 0.2)" : "rgba(16, 185, 129, 0.2)",
              color: isArmed ? "#ef4444" : "#10b981",
              border: `1px solid ${isArmed ? "rgba(239, 68, 68, 0.4)" : "rgba(16, 185, 129, 0.4)"}`,
            }}
          >
            {isArmed ? "🔴 ARMED" : "🟢 DISARMED"}
          </span>
          <span
            style={{
              fontSize: "0.7rem",
              fontFamily: "monospace",
              padding: "0.15rem 0.45rem",
              borderRadius: "4px",
              background: "rgba(0, 240, 255, 0.15)",
              color: "#00F0FF",
              border: "1px solid rgba(0, 240, 255, 0.3)",
            }}
          >
            {currentState}
          </span>
        </div>
      </div>

      {/* Main Content Area (Scrollable if needed) */}
      <div style={{ padding: "0.75rem", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: "0.65rem" }}>
        {/* Status Message Banner */}
        {stepMsg && (
          <div
            style={{
              padding: "0.4rem 0.65rem",
              fontSize: "0.75rem",
              borderRadius: "4px",
              background: stepMsg.startsWith("❌") ? "rgba(239, 68, 68, 0.15)" : stepMsg.startsWith("⚠️") ? "rgba(245, 158, 11, 0.15)" : "rgba(16, 185, 129, 0.15)",
              border: `1px solid ${stepMsg.startsWith("❌") ? "rgba(239, 68, 68, 0.4)" : stepMsg.startsWith("⚠️") ? "rgba(245, 158, 11, 0.4)" : "rgba(16, 185, 129, 0.4)"}`,
              color: stepMsg.startsWith("❌") ? "#fca5a5" : stepMsg.startsWith("⚠️") ? "#fde68a" : "#86efac",
            }}
          >
            {stepMsg}
          </div>
        )}

        {/* ── SECTION 1: ARM / DISARM BAR ────────────────────────── */}
        <div style={{ background: "rgba(8, 14, 28, 0.6)", padding: "0.5rem", borderRadius: "6px", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
            <span style={{ fontSize: "0.7rem", color: "#94a3b8", fontWeight: 700, letterSpacing: "0.5px" }}>
              ⚡ KHÓA / MỞ ĐỘNG CƠ (MOTOR ARMING)
            </span>
            <span style={{ fontSize: "0.65rem", color: "#64748b" }}>Mode: {flightMode}</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1.2fr", gap: "6px" }}>
            <button
              id="btn-manual-arm"
              className="btn btn-arm"
              style={{ padding: "0.35rem 0.5rem", fontSize: "0.75rem" }}
              disabled={isArmed || armLoading !== null || !droneOnline}
              onClick={handleArm}
              title={isArmed ? "Đã khóa mô-tơ" : "Mở khóa động cơ"}
            >
              {armLoading === "arm" ? "Arming…" : "⚡ ARM ĐỘNG CƠ"}
            </button>
            <button
              id="btn-manual-disarm"
              className="btn btn-disarm"
              style={{ padding: "0.35rem 0.5rem", fontSize: "0.75rem" }}
              disabled={!isArmed || armLoading !== null || !droneOnline}
              onClick={() => handleDisarm(false)}
              title={!isArmed ? "Đã tắt mô-tơ" : "Tắt mô-tơ an toàn"}
            >
              {armLoading === "disarm" ? "Disarming…" : "🛑 DISARM"}
            </button>
            <button
              id="btn-force-disarm"
              className="btn btn-force-disarm"
              style={{ padding: "0.35rem 0.5rem", fontSize: "0.72rem" }}
              disabled={armLoading !== null || !droneOnline}
              onClick={() => handleDisarm(true)}
              title="⚠️ Khẩn cấp ngắt mô-tơ lập tức"
            >
              {armLoading === "force" ? "Forcing…" : "☠️ FORCE DISARM"}
            </button>
          </div>
        </div>

        {/* ── SECTION 2: QUICK MODES & CAMERA ───────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "6px" }}>
          {/* Quick PX4 Modes */}
          <div style={{ background: "rgba(8, 14, 28, 0.6)", padding: "0.5rem", borderRadius: "6px", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
            <span style={{ fontSize: "0.68rem", color: "#94a3b8", fontWeight: 700, display: "block", marginBottom: "0.35rem" }}>
              CHẾ ĐỘ BAY NHANH (PX4 MODES)
            </span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px" }}>
              {FLIGHT_MODES.map((mode) => {
                const active = isModeActive(mode.value, droneStatus?.flight_mode, droneStatus?.drone_state);
                return (
                  <button
                    key={mode.value}
                    onClick={() => handleSetMode(mode.value)}
                    className={`btn-mode mode-${mode.value.toLowerCase()} ${active ? "active" : ""}`}
                    style={{ padding: "0.3rem 0.4rem", fontSize: "0.7rem" }}
                    title={mode.desc}
                    disabled={!droneOnline}
                  >
                    {mode.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Camera Controls */}
          <div style={{ background: "rgba(8, 14, 28, 0.6)", padding: "0.5rem", borderRadius: "6px", border: "1px solid rgba(255, 255, 255, 0.06)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.68rem", color: "#94a3b8", fontWeight: 700, display: "block", marginBottom: "0.35rem" }}>
              CAMERA VISION
            </span>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <button
                onClick={() => handleCamera("start")}
                className="btn btn-cam-start"
                style={{ padding: "0.3rem 0.4rem", fontSize: "0.7rem", width: "100%" }}
                disabled={!droneOnline}
              >
                📷 Bật Camera
              </button>
              <button
                onClick={() => handleCamera("stop")}
                className="btn btn-cam-stop"
                style={{ padding: "0.3rem 0.4rem", fontSize: "0.7rem", width: "100%" }}
                disabled={!droneOnline}
              >
                ⏹ Tắt Camera
              </button>
            </div>
          </div>
        </div>

        {/* ── SECTION 3: 7-STEP FLIGHT PIPELINE ─────────────────── */}
        <div style={{ background: "rgba(8, 14, 28, 0.6)", padding: "0.5rem", borderRadius: "6px", border: "1px solid rgba(0, 240, 255, 0.15)", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.72rem", color: "#00F0FF", fontWeight: 700 }}>
              🪜 QUY TRÌNH BAY TỪNG BƯỚC (STEP PIPELINE)
            </span>
            <span style={{ fontSize: "0.65rem", color: "#64748b" }}>Kích hoạt độc lập từng pha bay</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {/* Step 1 & 2 in 1 row */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px" }}>
              {/* Step 1: IDLE */}
              <div className="step-card" style={{ padding: "6px 8px" }}>
                <div className="step-num" style={{ width: "20px", height: "20px", fontSize: "0.7rem" }}>1</div>
                <div className="step-info" style={{ flex: 1 }}>
                  <strong style={{ fontSize: "0.72rem" }}>Reset IDLE</strong>
                  <span style={{ fontSize: "0.65rem" }}>Phục hồi FSM</span>
                </div>
                <button
                  type="button"
                  className="btn btn-step"
                  style={{ padding: "0.2rem 0.5rem", fontSize: "0.68rem" }}
                  onClick={() => handleStepAction("RESET_IDLE")}
                  disabled={armLoading !== null || !droneOnline}
                >
                  Reset
                </button>
              </div>

              {/* Step 2: TAKEOFF */}
              <div className="step-card" style={{ padding: "6px 8px" }}>
                <div className="step-num" style={{ width: "20px", height: "20px", fontSize: "0.7rem" }}>2</div>
                <div className="step-info" style={{ flex: 1 }}>
                  <strong style={{ fontSize: "0.72rem" }}>TAKEOFF (1.5m)</strong>
                  <span style={{ fontSize: "0.65rem" }}>Cất cánh giữ vị trí</span>
                </div>
                <button
                  type="button"
                  className="btn btn-step primary"
                  style={{ padding: "0.2rem 0.5rem", fontSize: "0.68rem" }}
                  onClick={() => handleStepAction("TAKEOFF", { alt: 1.5 })}
                  disabled={!isArmed || armLoading !== null || !droneOnline}
                >
                  Cất cánh
                </button>
              </div>
            </div>

            {/* Step 3: NAV_GPS (Full Width with compact target selector) */}
            <div className="step-card" style={{ padding: "6px 8px", flexDirection: "column", alignItems: "stretch", background: "rgba(15, 23, 42, 0.75)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div className="step-num" style={{ width: "20px", height: "20px", fontSize: "0.7rem" }}>3</div>
                <div className="step-info" style={{ flex: 1 }}>
                  <strong style={{ fontSize: "0.72rem" }}>🎯 Bay GPS vị trí (`LOITER` + `DO_REPOSITION`)</strong>
                </div>
              </div>

              <div style={{ display: "flex", gap: "4px", marginTop: "4px", alignItems: "center", flexWrap: "wrap" }}>
                <select
                  className="form-input"
                  style={{ flex: 1, minWidth: "120px", padding: "0.2rem 0.4rem", fontSize: "0.7rem" }}
                  value={targetType}
                  onChange={(e) => setTargetType(e.target.value as any)}
                >
                  <option value="pickup">📦 Điểm Lấy hàng</option>
                  <option value="drop">📬 Điểm Giao hàng</option>
                  <option value="home">🏠 Trạm Kho (Home)</option>
                  <option value="custom">📍 Tọa độ tùy chỉnh</option>
                </select>

                {targetType === "custom" && (
                  <>
                    <input
                      type="number"
                      step="0.000001"
                      placeholder="Lat"
                      className="form-input"
                      style={{ width: "85px", padding: "0.2rem 0.35rem", fontSize: "0.7rem" }}
                      value={customLat}
                      onChange={(e) => setCustomLat(parseFloat(e.target.value) || 0)}
                    />
                    <input
                      type="number"
                      step="0.000001"
                      placeholder="Lon"
                      className="form-input"
                      style={{ width: "85px", padding: "0.2rem 0.35rem", fontSize: "0.7rem" }}
                      value={customLon}
                      onChange={(e) => setCustomLon(parseFloat(e.target.value) || 0)}
                    />
                  </>
                )}

                <span style={{ fontSize: "0.68rem", color: "#94a3b8" }}>Cao:</span>
                <input
                  type="number"
                  step="0.1"
                  className="form-input"
                  style={{ width: "48px", padding: "0.2rem 0.3rem", fontSize: "0.7rem" }}
                  value={targetAlt}
                  onChange={(e) => setTargetAlt(parseFloat(e.target.value) || 1.5)}
                />

                <button
                  type="button"
                  className="btn btn-step primary"
                  style={{ padding: "0.2rem 0.55rem", fontSize: "0.68rem" }}
                  onClick={() => handleStepAction("NAV_GPS")}
                  disabled={!isArmed || armLoading !== null || !droneOnline}
                >
                  Bay GPS
                </button>
              </div>
            </div>

            {/* Step 4 & 5 in 1 row */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px" }}>
              {/* Step 4: DESCEND */}
              <div className="step-card" style={{ padding: "6px 8px" }}>
                <div className="step-num" style={{ width: "20px", height: "20px", fontSize: "0.7rem" }}>4</div>
                <div className="step-info" style={{ flex: 1 }}>
                  <strong style={{ fontSize: "0.72rem" }}>DESCEND (1.0m)</strong>
                  <span style={{ fontSize: "0.65rem" }}>Hạ rà Marker</span>
                </div>
                <button
                  type="button"
                  className="btn btn-step"
                  style={{ padding: "0.2rem 0.5rem", fontSize: "0.68rem" }}
                  onClick={() => handleStepAction("DESCEND", { alt: 1.0 })}
                  disabled={!isArmed || armLoading !== null || !droneOnline}
                >
                  Hạ 1.0m
                </button>
              </div>

              {/* Step 5: SEARCH_ARUCO */}
              <div className="step-card" style={{ padding: "6px 8px" }}>
                <div className="step-num" style={{ width: "20px", height: "20px", fontSize: "0.7rem" }}>5</div>
                <div className="step-info" style={{ flex: 1 }}>
                  <strong style={{ fontSize: "0.72rem" }}>SEARCH ARUCO</strong>
                  <span style={{ fontSize: "0.65rem" }}>Bật Camera rà</span>
                </div>
                <button
                  type="button"
                  className="btn btn-step"
                  style={{ padding: "0.2rem 0.5rem", fontSize: "0.68rem" }}
                  onClick={() => handleStepAction("SEARCH_ARUCO")}
                  disabled={armLoading !== null || !droneOnline}
                >
                  Rà Marker
                </button>
              </div>
            </div>

            {/* Step 6 & 7 in 1 row */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px" }}>
              {/* Step 6: PRECISION_LANDING */}
              <div className="step-card" style={{ padding: "6px 8px" }}>
                <div className="step-num" style={{ width: "20px", height: "20px", fontSize: "0.7rem" }}>6</div>
                <div className="step-info" style={{ flex: 1 }}>
                  <strong style={{ fontSize: "0.72rem" }}>PRECLAND</strong>
                  <span style={{ fontSize: "0.65rem" }}>Đáp ArUco</span>
                </div>
                <button
                  type="button"
                  className="btn btn-step success"
                  style={{ padding: "0.2rem 0.5rem", fontSize: "0.68rem" }}
                  onClick={() => handleStepAction("PRECISION_LANDING")}
                  disabled={!isArmed || armLoading !== null || !droneOnline}
                >
                  Đáp ArUco
                </button>
              </div>

              {/* Step 7: NORMAL_LANDING */}
              <div className="step-card" style={{ padding: "6px 8px" }}>
                <div className="step-num" style={{ width: "20px", height: "20px", fontSize: "0.7rem" }}>7</div>
                <div className="step-info" style={{ flex: 1 }}>
                  <strong style={{ fontSize: "0.72rem" }}>LAND THƯỜNG</strong>
                  <span style={{ fontSize: "0.65rem" }}>Auto Land PX4</span>
                </div>
                <button
                  type="button"
                  className="btn btn-step warning"
                  style={{ padding: "0.2rem 0.5rem", fontSize: "0.68rem" }}
                  onClick={() => handleStepAction("NORMAL_LANDING")}
                  disabled={!isArmed || armLoading !== null || !droneOnline}
                >
                  Hạ thường
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
