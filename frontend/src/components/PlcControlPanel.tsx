import { useState } from "react";
import type { PLCState } from "../types/drone";
import {
  controlPlcHatch,
  controlPlcLock,
  setSimulatedDroneSensor,
  startPlc,
  stopPlc,
  resetPlc,
} from "../services/api";

interface Props {
  plc: PLCState | null;
}

export function PlcControlPanel({ plc }: Props) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const handleSystemCmd = async (action: "START" | "STOP" | "RESET") => {
    setLoading(true);
    setMsg(null);
    try {
      let res: Response;
      if (action === "START") res = await startPlc();
      else if (action === "STOP") res = await stopPlc();
      else res = await resetPlc();

      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || `Lệnh ${action} PLC thành công!`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleHatch = async (open: boolean) => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await controlPlcHatch(open);
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || `Lệnh ${open ? "Nâng Trục Z" : "Hạ Trục Z"} thành công!`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleLock = async (lock: boolean) => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await controlPlcLock(lock);
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || `Lệnh ${lock ? "Khóa" : "Mở khóa"} thành công!`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSensor = async (detected: boolean) => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await setSimulatedDroneSensor(detected);
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || `Cảm biến đã đặt: ${detected ? "CÓ DRONE" : "TRỐNG"}`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel plc-panel">
      <div className="panel-header-inline">
        <h3>⚡ Điều khiển Docking PLC S7-1200 (DB15 Mapping)</h3>
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <span className={`status-badge ${plc?.connected ? "status-online" : "status-offline"}`}>
            {plc?.connected ? "KẾT NỐI" : "MẤT KẾT NỐI"}
          </span>
          <span className={`status-badge ${plc?.plc_on ? "status-online" : "status-offline"}`}>
            {plc?.plc_on ? "PLC READY" : "PLC STOPPED"}
          </span>
          {plc?.simulator_mode && (
            <span className="status-badge status-busy" title="Đang chạy chế độ mô phỏng, không kết nối PLC thật">
              SIM
            </span>
          )}
        </div>
      </div>

      {/* DB15 Byte 2 Status Bits Grid (PLC -> Backend) */}
      <div style={{ fontSize: "12px", fontWeight: "bold", marginBottom: "6px", color: "var(--text-secondary)" }}>
        📊 Trạng thái PLC → Backend (DB15 Byte 2 Bits):
      </div>
      <div className="sensor-grid">
        <div className={`sensor-item ${plc?.drone_detected ? "active-orange" : "inactive"}`}>
          <span className="sensor-icon">🛬</span>
          <span className="sensor-label">drone_detected (DB15.DBX2.0)</span>
          <span className="sensor-value">{plc?.drone_detected ? "CÓ DRONE" : "TRỐNG"}</span>
        </div>

        <div className={`sensor-item ${plc?.plc_locked_state ? "active-blue" : "inactive"}`}>
          <span className="sensor-icon">🔒</span>
          <span className="sensor-label">plc_locked_state (DB15.DBX2.1)</span>
          <span className="sensor-value">{plc?.plc_locked_state ? "ĐÃ KHÓA" : "MỞ KHÓA"}</span>
        </div>

        <div className={`sensor-item ${plc?.plc_z_is_up ? "active-green" : "inactive"}`}>
          <span className="sensor-icon">⬆️</span>
          <span className="sensor-label">plc_z_is_up (DB15.DBX2.2)</span>
          <span className="sensor-value">{plc?.plc_z_is_up ? "VỊ TRÍ TRÊN (UP)" : "OFF"}</span>
        </div>

        <div className={`sensor-item ${plc?.plc_z_is_down ? "active-green" : "inactive"}`}>
          <span className="sensor-icon">⬇️</span>
          <span className="sensor-label">plc_z_is_down (DB15.DBX2.3)</span>
          <span className="sensor-value">{plc?.plc_z_is_down ? "VỊ TRÍ DƯỚI (DOWN)" : "OFF"}</span>
        </div>

        <div className={`sensor-item ${plc?.plc_on ? "active-green" : "inactive"}`}>
          <span className="sensor-icon">⚡</span>
          <span className="sensor-label">plc_on (DB15.DBX2.4)</span>
          <span className="sensor-value">{plc?.plc_on ? "ACTIVE & READY" : "STOPPED"}</span>
        </div>

        <div className={`sensor-item ${plc?.plc_error ? "active-red" : "inactive"}`}>
          <span className="sensor-icon">⚠️</span>
          <span className="sensor-label">plc_error (DB15.DBX2.5)</span>
          <span className="sensor-value">{plc?.plc_error ? "LỖI HỆ THỐNG" : "BÌNH THƯỜNG"}</span>
        </div>

        <div className={`sensor-item ${plc?.emergency_stop ? "active-red" : "inactive"}`}>
          <span className="sensor-icon">🚨</span>
          <span className="sensor-label">emergency_stop (DB15.DBX2.6)</span>
          <span className="sensor-value">{plc?.emergency_stop ? "E-STOP ACTIVE" : "NORMAL"}</span>
        </div>
      </div>

      {/* Z-Axis status indicator */}
      <div className="plc-z-axis-status" style={{ marginTop: "10px" }}>
        <span className="font-bold">Trạng thái Trục Z:</span>{" "}
        <span className={`status-badge ${
          plc?.z_axis === "UP" ? "status-online" :
          plc?.z_axis === "DOWN" ? "status-online" :
          plc?.z_axis === "MOVING" ? "status-busy" :
          "status-offline"
        }`}>
          {plc?.z_axis === "UP" ? "⬆️ VỊ TRÍ TRÊN (UP)" :
           plc?.z_axis === "DOWN" ? "⬇️ VỊ TRÍ DƯỚI (DOWN)" :
           plc?.z_axis === "MOVING" ? "🔄 ĐANG DI CHUYỂN (MOVING)" :
           "🏠 BAN ĐẦU (HOME)"}
        </span>
      </div>

      {/* DB15 Byte 0 Commands (Backend -> PLC) */}
      <div style={{ fontSize: "12px", fontWeight: "bold", marginTop: "12px", marginBottom: "6px", color: "var(--text-secondary)" }}>
        🎮 Lệnh Điều khiển Backend → PLC (DB15 Byte 0 Commands):
      </div>

      {/* System Control Commands */}
      <div className="plc-action-buttons" style={{ marginBottom: "8px" }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => handleSystemCmd("START")}
          disabled={loading || plc?.plc_busy}
          title="Gửi cmd_start_plc (DB15.DBX0.5)"
        >
          🚀 Start PLC (DBX0.5)
        </button>
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => handleSystemCmd("STOP")}
          disabled={loading || plc?.plc_busy}
          title="Gửi cmd_stop_plc (DB15.DBX0.4)"
        >
          🛑 Stop PLC (DBX0.4)
        </button>
        <button
          type="button"
          className="btn btn-warning"
          onClick={() => handleSystemCmd("RESET")}
          disabled={loading || plc?.plc_busy}
          title="Gửi cmd_reset_plc (DB15.DBX0.6)"
        >
          🔄 Reset Fault (DBX0.6)
        </button>
      </div>

      {/* Mechanical Mechanism Commands */}
      <div className="plc-action-buttons">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => handleLock(true)}
          disabled={loading || plc?.plc_busy || !plc?.plc_on}
          title="Gửi cmd_lock_drone (DB15.DBX0.0)"
        >
          🔒 Lock Drone (DBX0.0)
        </button>
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => handleLock(false)}
          disabled={loading || plc?.plc_busy || !plc?.plc_on}
          title="Gửi cmd_unlock_drone (DB15.DBX0.1)"
        >
          🔓 Unlock Drone (DBX0.1)
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => handleHatch(true)}
          disabled={loading || plc?.plc_busy || !plc?.plc_on}
          title="Gửi cmd_z_up (DB15.DBX0.2)"
        >
          ⬆️ Lift Z Up (DBX0.2)
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => handleHatch(false)}
          disabled={loading || plc?.plc_busy || !plc?.plc_on}
          title="Gửi cmd_z_down (DB15.DBX0.3)"
        >
          ⬇️ Lift Z Down (DBX0.3)
        </button>
        <button
          type="button"
          className={`btn ${plc?.drone_detected ? "btn-outline" : "btn-warning"}`}
          onClick={() => handleToggleSensor(!plc?.drone_detected)}
          disabled={loading}
          title="Mô phỏng cảm biến phát hiện drone (DB15.DBX2.0)"
        >
          🛬 {plc?.drone_detected ? "Mô phỏng: Báo Trống" : "Mô phỏng: Báo Có Drone"}
        </button>
      </div>

      {msg && <div className="panel-msg">{msg}</div>}
    </div>
  );
}
