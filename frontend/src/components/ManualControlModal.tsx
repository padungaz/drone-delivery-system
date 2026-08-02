import { useState } from "react";
import {
  setFlightMode,
  startCamera,
  stopCamera,
  armDrone,
  disarmDrone,
  sendStepCommand,
} from "../services/api";
import type { MissionLocations } from "../types/drone";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  droneStatus?: any;
  locations?: MissionLocations;
};

const FLIGHT_MODES = [
  { label: "🟡 Hold / Loiter", value: "LOITER", desc: "Chế độ định vị giữ vị trí & bay tới đích (DO_REPOSITION)" },
  { label: "🛫 Takeoff", value: "TAKEOFF", desc: "Cất cánh tự động lên độ cao an toàn" },
  { label: "🛬 Land", value: "LAND", desc: "Hạ cánh tự động tại vị trí hiện tại" },
  { label: "🏠 Return (RTL)", value: "RTL", desc: "Bay quay về Trạm xuất phát và đáp" },
];

export function ManualControlModal({ isOpen, onClose, droneStatus, locations }: Props) {
  const [armLoading, setArmLoading] = useState<string | null>(null);
  const [stepMsg, setStepMsg] = useState<string | null>(null);

  // GPS target choice for Step 4 (NAV_GPS)
  const [targetType, setTargetType] = useState<"home" | "pickup" | "drop" | "custom">("pickup");
  const [customLat, setCustomLat] = useState<number>(16.0544);
  const [customLon, setCustomLon] = useState<number>(108.2022);
  const [targetAlt, setTargetAlt] = useState<number>(4.0);

  if (!isOpen) return null;

  const isArmed: boolean = droneStatus?.armed ?? false;
  const currentState: string = droneStatus?.drone_state || "IDLE";

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
      setStepMsg(res.ok ? `✅ Đã yêu cầu chế độ ${mode}` : `❌ ${data.detail ?? "Lỗi đặt chế độ"}`);
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
      setStepMsg("❌ Lỗi mạng");
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
      setStepMsg("❌ Lỗi mạng");
    } finally {
      setArmLoading(null);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: "700px", width: "95%" }}>
        <button onClick={onClose} className="modal-close" title="Đóng">✕</button>

        {/* Header Section */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem", borderBottom: "1px solid var(--border)", paddingBottom: "0.75rem" }}>
          <h2>🎮 Bảng Điều khiển & Kiểm thử Drone</h2>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span className={`armed-badge ${isArmed ? "armed" : "disarmed"}`}>
              {isArmed ? "🔴 ARMED" : "🟢 DISARMED"}
            </span>
            <span className="badge online" style={{ fontSize: "12px" }}>
              {currentState}
            </span>
          </div>
        </div>

        {stepMsg && <p className="action-message" style={{ marginBottom: "1rem" }}>{stepMsg}</p>}

        {/* ── SECTION 1: ARM / DISARM CONTROLS ──────────────────────────── */}
        <div className="modal-section" style={{ marginBottom: "1.2rem" }}>
          <div className="arm-controls">
            <button
              id="btn-manual-arm"
              className="btn btn-arm"
              disabled={isArmed || armLoading !== null}
              onClick={handleArm}
              title={isArmed ? "Đã khóa mô-tơ" : "Mở khóa động cơ"}
            >
              {armLoading === "arm" ? "Arming…" : "⚡ ARM ĐỘNG CƠ"}
            </button>
            <button
              id="btn-manual-disarm"
              className="btn btn-disarm"
              disabled={!isArmed || armLoading !== null}
              onClick={() => handleDisarm(false)}
              title={!isArmed ? "Đã tắt mô-tơ" : "Tắt mô-tơ"}
            >
              {armLoading === "disarm" ? "Disarming…" : "🛑 DISARM"}
            </button>
            <button
              id="btn-force-disarm"
              className="btn btn-force-disarm"
              disabled={armLoading !== null}
              onClick={() => handleDisarm(true)}
              title="⚠️ Khẩn cấp ngắt mô-tơ lập tức"
            >
              {armLoading === "force" ? "Forcing…" : "☠️ FORCE DISARM"}
            </button>
          </div>
        </div>

        {/* ── SECTION 2: STEP-BY-STEP PIPELINE ──────────────────────────── */}
        <div className="step-pipeline-wrapper" style={{ marginBottom: "1.2rem" }}>
          <h3 style={{ marginBottom: "0.5rem" }}>🪜 Quy trình Bay từng bước (Step Pipeline)</h3>
          <p className="warning-text" style={{ marginBottom: "0.8rem" }}>
            Kích hoạt độc lập từng bước trong quy trình tự động để kiểm tra & cân chỉnh cảm biến.
          </p>

          <div className="step-grid">
            {/* Step 1: IDLE */}
            <div className="step-card">
              <div className="step-num">1</div>
              <div className="step-info">
                <strong>🔴 Reset về IDLE</strong>
                <span>Khôi phục FSM về trạng thái nghỉ</span>
              </div>
              <button
                type="button"
                className="btn btn-step"
                onClick={() => handleStepAction("RESET_IDLE")}
                disabled={armLoading !== null}
              >
                Reset IDLE
              </button>
            </div>

            {/* Step 2: TAKEOFF */}
            <div className="step-card">
              <div className="step-num">2</div>
              <div className="step-info">
                <strong>🛫 TAKEOFF (Giữ vị trí)</strong>
                <span>Cất cánh thẳng đứng & giữ cố định 4m</span>
              </div>
              <button
                type="button"
                className="btn btn-step primary"
                onClick={() => handleStepAction("TAKEOFF", { alt: 4.0 })}
                disabled={!isArmed || armLoading !== null}
              >
                Cất cánh (4m)
              </button>
            </div>

            {/* Step 3: NAV_GPS */}
            <div className="step-card" style={{ gridColumn: "1 / -1", background: "rgba(15, 23, 42, 0.6)", padding: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", width: "100%" }}>
                <div className="step-num">3</div>
                <div className="step-info" style={{ flex: 1 }}>
                  <strong>🎯 Bay GPS vị trí chỉ định (`LOITER`)</strong>
                  <span>Bay định hướng GPS & giữ vị trí tự động qua `MAV_CMD_DO_REPOSITION` (4m)</span>
                </div>
              </div>

              <div style={{ display: "flex", gap: "10px", marginTop: "10px", alignItems: "center", flexWrap: "wrap" }}>
                <select
                  className="form-input"
                  style={{ width: "auto", minWidth: "160px", padding: "0.35rem 0.6rem" }}
                  value={targetType}
                  onChange={(e) => setTargetType(e.target.value as any)}
                >
                  <option value="pickup">📦 Điểm Lấy hàng</option>
                  <option value="drop">📬 Điểm Giao hàng</option>
                  <option value="home">🏠 Trạm xuất phát (Kho)</option>
                  <option value="custom">📍 Tọa độ tùy chỉnh</option>
                </select>

                {targetType === "custom" && (
                  <>
                    <input
                      type="number"
                      step="0.000001"
                      placeholder="Lat"
                      className="form-input"
                      style={{ width: "110px", padding: "0.35rem" }}
                      value={customLat}
                      onChange={(e) => setCustomLat(parseFloat(e.target.value) || 0)}
                    />
                    <input
                      type="number"
                      step="0.000001"
                      placeholder="Lon"
                      className="form-input"
                      style={{ width: "110px", padding: "0.35rem" }}
                      value={customLon}
                      onChange={(e) => setCustomLon(parseFloat(e.target.value) || 0)}
                    />
                  </>
                )}

                <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Cao (m):</span>
                <input
                  type="number"
                  step="0.5"
                  className="form-input"
                  style={{ width: "70px", padding: "0.35rem" }}
                  value={targetAlt}
                  onChange={(e) => setTargetAlt(parseFloat(e.target.value) || 4.0)}
                />

                <button
                  type="button"
                  className="btn btn-step primary"
                  onClick={() => handleStepAction("NAV_GPS")}
                  disabled={!isArmed || armLoading !== null}
                >
                  Bay GPS (`LOITER`)
                </button>
              </div>
            </div>

            {/* Step 4: DESCEND */}
            <div className="step-card">
              <div className="step-num">4</div>
              <div className="step-info">
                <strong>📉 DESCEND (Hạ tiếp cận)</strong>
                <span>Hạ cao độ rà tìm xuống 2.5m</span>
              </div>
              <button
                type="button"
                className="btn btn-step"
                onClick={() => handleStepAction("DESCEND", { alt: 2.5 })}
                disabled={!isArmed || armLoading !== null}
              >
                Hạ cao độ (2.5m)
              </button>
            </div>

            {/* Step 5: SEARCH_ARUCO */}
            <div className="step-card">
              <div className="step-num">5</div>
              <div className="step-info">
                <strong>📷 SEARCH ARUCO (Rà Marker)</strong>
                <span>Bật Camera rà mã ArUco</span>
              </div>
              <button
                type="button"
                className="btn btn-step"
                onClick={() => handleStepAction("SEARCH_ARUCO")}
                disabled={armLoading !== null}
              >
                Bật Rà ArUco
              </button>
            </div>

            {/* Step 6: PRECISION_LANDING */}
            <div className="step-card">
              <div className="step-num">6</div>
              <div className="step-info">
                <strong>🎯 PRECISION LANDING</strong>
                <span>Hạ cánh căn chỉnh theo ArUco (&lt;20cm)</span>
              </div>
              <button
                type="button"
                className="btn btn-step success"
                onClick={() => handleStepAction("PRECISION_LANDING")}
                disabled={!isArmed || armLoading !== null}
              >
                Hạ cánh ArUco
              </button>
            </div>

            {/* Step 7: NORMAL_LANDING */}
            <div className="step-card">
              <div className="step-num">7</div>
              <div className="step-info">
                <strong>🛬 NORMAL LANDING (Hạ thường)</strong>
                <span>PX4 Auto Land tại chỗ</span>
              </div>
              <button
                type="button"
                className="btn btn-step warning"
                onClick={() => handleStepAction("NORMAL_LANDING")}
                disabled={!isArmed || armLoading !== null}
              >
                Hạ thường (Land)
              </button>
            </div>
          </div>
        </div>

        {/* ── SECTION 3: QUICK FLIGHT MODES & CAMERA CONTROLS ──────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "1rem" }}>
          <div className="modal-section">
            <h3 style={{ marginBottom: "0.5rem" }}>Chế độ bay Nhanh (PX4 Modes)</h3>
            <div className="modal-grid-2" style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "8px" }}>
              {FLIGHT_MODES.map((mode) => (
                <button
                  key={mode.value}
                  onClick={() => handleSetMode(mode.value)}
                  className={`btn-mode ${droneStatus?.flight_mode === mode.value ? "active" : ""}`}
                  title={mode.desc}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>

          <div className="modal-section">
            <h3 style={{ marginBottom: "0.5rem" }}>Camera Vision</h3>
            <div className="camera-controls" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <button onClick={() => handleCamera("start")} className="btn btn-cam-start">Bật Camera</button>
              <button onClick={() => handleCamera("stop")} className="btn btn-cam-stop">Tắt Camera</button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
