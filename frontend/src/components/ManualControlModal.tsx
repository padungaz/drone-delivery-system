import { useState } from "react";
import {
  setFlightMode,
  moveRelative,
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
  { label: "⚡ Offboard", value: "OFFBOARD", desc: "Chế độ điều khiển hướng từ Pi 5" },
  { label: "🟡 Hold / Loiter", value: "LOITER", desc: "Duy trì vị trí & độ cao cố định" },
  { label: "🛫 Takeoff", value: "TAKEOFF", desc: "Cất cánh tự động lên độ cao an toàn" },
  { label: "🛬 Land", value: "LAND", desc: "Hạ cánh tự động tại vị trí hiện tại" },
  { label: "🏠 Return (RTL)", value: "RTL", desc: "Bay quay về Trạm xuất phát và đáp" },
];

export function ManualControlModal({ isOpen, onClose, droneStatus, locations }: Props) {
  const [activeTab, setActiveTab] = useState<"step" | "advanced">("step");
  const [armLoading, setArmLoading] = useState<string | null>(null);
  const [stepMsg, setStepMsg] = useState<string | null>(null);

  // GPS target choice for Step 4 (NAV_GPS)
  const [targetType, setTargetType] = useState<"home" | "pickup" | "drop" | "custom">("pickup");
  const [customLat, setCustomLat] = useState<number>(16.0544);
  const [customLon, setCustomLon] = useState<number>(108.2022);
  const [targetAlt, setTargetAlt] = useState<number>(10.0);

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
    if ((mode === "OFFBOARD" || mode === "TAKEOFF") && !isArmed) {
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

  const handleMove = async (dx: number, dy: number, dz: number) => {
    try {
      await moveRelative(dx, dy, dz);
    } catch (err) {
      console.error("Failed to move", err);
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
      <div className="modal-content" style={{ maxWidth: "680px", width: "95%" }}>
        <button onClick={onClose} className="modal-close" title="Đóng">✕</button>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
          <h2>🎮 Điều khiển Thủ công Drone</h2>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span className={`armed-badge ${isArmed ? "armed" : "disarmed"}`}>
              {isArmed ? "🔴 ARMED" : "🟢 DISARMED"}
            </span>
            <span className="badge online" style={{ fontSize: "12px" }}>
              {currentState}
            </span>
          </div>
        </div>

        {/* Modal Tab Switcher */}
        <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid var(--border)", marginBottom: "1.2rem", paddingBottom: "0.5rem" }}>
          <button
            type="button"
            className={`btn-map-action ${activeTab === "step" ? "active" : ""}`}
            onClick={() => setActiveTab("step")}
            style={{ fontSize: "0.9rem", padding: "0.5rem 1rem" }}
          >
            🪜 Điều khiển từng bước (Step Pipeline)
          </button>
          <button
            type="button"
            className={`btn-map-action ${activeTab === "advanced" ? "active" : ""}`}
            onClick={() => setActiveTab("advanced")}
            style={{ fontSize: "0.9rem", padding: "0.5rem 1rem" }}
          >
            🎛️ Chế độ bay & Phím D-Pad
          </button>
        </div>

        {stepMsg && <p className="action-message" style={{ marginBottom: "1rem" }}>{stepMsg}</p>}

        {/* ── TAB 1: STEP-BY-STEP PIPELINE ───────────────────────────────── */}
        {activeTab === "step" && (
          <div className="step-pipeline-wrapper">
            <p className="warning-text" style={{ marginBottom: "1rem" }}>
              Kích hoạt độc lập từng bước riêng lẻ trong quy trình bay tự động để kiểm tra & cân chỉnh cảm biến.
            </p>

            <div className="step-grid">
              {/* Step 1: IDLE */}
              <div className="step-card">
                <div className="step-num">1</div>
                <div className="step-info">
                  <strong>🔴 Reset về IDLE</strong>
                  <span>Khôi phục FSM về trạng thái nghỉ ban đầu</span>
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

              {/* Step 2: ARMING */}
              <div className="step-card">
                <div className="step-num">2</div>
                <div className="step-info">
                  <strong>⚡ ARM / DISARM Động cơ</strong>
                  <span>Khóa an toàn & khởi động mô-tơ</span>
                </div>
                <div style={{ display: "flex", gap: "6px" }}>
                  <button
                    type="button"
                    className="btn btn-arm"
                    style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem" }}
                    onClick={handleArm}
                    disabled={isArmed || armLoading !== null}
                  >
                    ARM
                  </button>
                  <button
                    type="button"
                    className="btn btn-disarm"
                    style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem" }}
                    onClick={() => handleDisarm(false)}
                    disabled={!isArmed || armLoading !== null}
                  >
                    DISARM
                  </button>
                </div>
              </div>

              {/* Step 3: TAKEOFF */}
              <div className="step-card">
                <div className="step-num">3</div>
                <div className="step-info">
                  <strong>🛫 TAKEOFF (Giữ vị trí)</strong>
                  <span>Cất cánh thẳng đứng & giữ cố định độ cao ~2m</span>
                </div>
                <button
                  type="button"
                  className="btn btn-step primary"
                  onClick={() => handleStepAction("TAKEOFF", { alt: 2.0 })}
                  disabled={!isArmed || armLoading !== null}
                >
                  Cất cánh (2m)
                </button>
              </div>

              {/* Step 4: NAV_GPS */}
              <div className="step-card" style={{ gridColumn: "1 / -1", background: "rgba(15, 23, 42, 0.6)", padding: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", width: "100%" }}>
                  <div className="step-num">4</div>
                  <div className="step-info" style={{ flex: 1 }}>
                    <strong>🎯 Bay GPS tới vị trí chỉ định</strong>
                    <span>Bay định hướng GPS & tự động giữ vị trí (Loiter) khi tới nơi</span>
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
                    style={{ width: "65px", padding: "0.35rem" }}
                    value={targetAlt}
                    onChange={(e) => setTargetAlt(parseFloat(e.target.value) || 10)}
                  />

                  <button
                    type="button"
                    className="btn btn-step primary"
                    onClick={() => handleStepAction("NAV_GPS")}
                    disabled={!isArmed || armLoading !== null}
                  >
                    Bay GPS & Hover
                  </button>
                </div>
              </div>

              {/* Step 5: DESCEND */}
              <div className="step-card">
                <div className="step-num">5</div>
                <div className="step-info">
                  <strong>📉 DESCEND (Hạ độ cao tiếp cận)</strong>
                  <span>Hạ thấp độ cao rà tìm xuống ~4m & giữ vị trí</span>
                </div>
                <button
                  type="button"
                  className="btn btn-step"
                  onClick={() => handleStepAction("DESCEND", { alt: 4.0 })}
                  disabled={!isArmed || armLoading !== null}
                >
                  Hạ độ cao (4m)
                </button>
              </div>

              {/* Step 6: SEARCH_ARUCO */}
              <div className="step-card">
                <div className="step-num">6</div>
                <div className="step-info">
                  <strong>📷 SEARCH ARUCO (Rà tìm Marker)</strong>
                  <span>Bật Camera USB + thị giác máy tính rà ArUco</span>
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

              {/* Step 7: PRECISION_LANDING */}
              <div className="step-card">
                <div className="step-num">7</div>
                <div className="step-info">
                  <strong>🎯 PRECISION LANDING (ArUco)</strong>
                  <span>Hạ cánh chính xác căn chỉnh theo mã ArUco (&lt;20cm)</span>
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

              {/* Step 8: NORMAL_LANDING */}
              <div className="step-card">
                <div className="step-num">8</div>
                <div className="step-info">
                  <strong>🛬 NORMAL LANDING (Hạ thường)</strong>
                  <span>PX4 Auto Land thẳng đứng tại chỗ (Không ArUco)</span>
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
        )}

        {/* ── TAB 2: ADVANCED MODES & D-PAD ──────────────────────────────── */}
        {activeTab === "advanced" && (
          <div>
            {/* ── ARM / DISARM ─────────────────────────────────────── */}
            <div className="modal-section">
              <h3>
                Arm / Disarm&nbsp;
                <span className={`armed-badge ${isArmed ? "armed" : "disarmed"}`}>
                  {isArmed ? "🔴 ARMED" : "🟢 DISARMED"}
                </span>
              </h3>
              <div className="arm-controls">
                <button
                  id="btn-manual-arm"
                  className="btn btn-arm"
                  disabled={isArmed || armLoading !== null}
                  onClick={handleArm}
                  title={isArmed ? "Đã khóa mô-tơ" : "Mở khóa động cơ"}
                >
                  {armLoading === "arm" ? "Arming…" : "⚡ ARM"}
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

            {/* ── Flight Modes ─────────────────────────────────────── */}
            <div className="modal-section">
              <h3>Chế độ bay (PX4 Modes)</h3>
              <div className="modal-grid-3">
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

            {/* ── Movement ─────────────────────────────────────────── */}
            <div className="modal-section">
              <h3>Di chuyển phím D-Pad (10cm steps)</h3>
              <p className="warning-text">Yêu cầu chế độ OFFBOARD + ARMED.</p>
              <div className="movement-box">
                {/* Z axis */}
                <div className="z-axis-controls">
                  <button onClick={() => handleMove(0, 0, -0.1)} className="btn-move round" title="Up">UP</button>
                  <span className="z-label">Z-Axis</span>
                  <button onClick={() => handleMove(0, 0, 0.1)} className="btn-move round" title="Down">DN</button>
                </div>

                {/* X/Y axis (D-pad) */}
                <div className="modal-grid-dpad">
                  <div />
                  <button onClick={() => handleMove(0.1, 0, 0)} className="btn-move" title="Forward">▲</button>
                  <div />
                  <button onClick={() => handleMove(0, -0.1, 0)} className="btn-move" title="Left">◀</button>
                  <button onClick={() => handleMove(-0.1, 0, 0)} className="btn-move" title="Backward">▼</button>
                  <button onClick={() => handleMove(0, 0.1, 0)} className="btn-move" title="Right">▶</button>
                </div>
              </div>
            </div>

            {/* ── Camera ───────────────────────────────────────────── */}
            <div className="modal-section">
              <h3>Camera USB Vision</h3>
              <div className="camera-controls">
                <button onClick={() => handleCamera("start")} className="btn btn-cam-start">Bật Camera</button>
                <button onClick={() => handleCamera("stop")} className="btn btn-cam-stop">Tắt Camera</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
