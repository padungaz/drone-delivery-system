import { useState } from "react";
import type { PLCState } from "../types/drone";
import { controlPlcHatch, controlPlcLock } from "../services/api";

interface Props {
  plc: PLCState | null;
}

export function PlcControlPanel({ plc }: Props) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

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
      setMsg(data.message || `Lệnh ${open ? "Mở" : "Đóng"} nắp thành công!`);
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

  return (
    <div className="panel plc-panel">
      <div className="panel-header-inline">
        <h3>⚡ Điều khiển Docking PLC S7-1200</h3>
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <span className={`status-badge ${plc?.connected ? "status-online" : "status-offline"}`}>
            {plc?.connected ? "KẾT NỐI" : "MẤT KẾT NỐI"}
          </span>
          {plc?.simulator_mode && (
            <span className="status-badge status-busy" title="Đang chạy chế độ mô phỏng, không kết nối PLC thật">
              SIM
            </span>
          )}
        </div>
      </div>

      {/* Sensor Indicators — 2x3 grid */}
      <div className="sensor-grid">
        <div className={`sensor-item ${plc?.hatch_open ? "active-green" : "inactive"}`}>
          <span className="sensor-icon">📂</span>
          <span className="sensor-label">Nắp Docking</span>
          <span className="sensor-value">{plc?.hatch_open ? "ĐANG MỞ" : "ĐÃ ĐÓNG"}</span>
        </div>

        <div className={`sensor-item ${plc?.drone_locked ? "active-blue" : "inactive"}`}>
          <span className="sensor-icon">🔒</span>
          <span className="sensor-label">Khóa Khung Drone</span>
          <span className="sensor-value">{plc?.drone_locked ? "ĐÃ KHÓA" : "MỞ KHÓA"}</span>
        </div>

        <div className={`sensor-item ${plc?.drone_landed_sensor ? "active-orange" : "inactive"}`}>
          <span className="sensor-icon">🛬</span>
          <span className="sensor-label">Cảm biến Chạm sàn</span>
          <span className="sensor-value">{plc?.drone_landed_sensor ? "CÓ DRONE" : "TRỐNG"}</span>
        </div>

        <div className={`sensor-item ${plc?.emergency_stop ? "active-red" : "inactive"}`}>
          <span className="sensor-icon">⚠️</span>
          <span className="sensor-label">Dừng khẩn cấp</span>
          <span className="sensor-value">{plc?.emergency_stop ? "TRIGGERED" : "NORMAL"}</span>
        </div>

        <div className={`sensor-item ${plc?.plc_busy ? "active-orange" : "inactive"}`}>
          <span className="sensor-icon">⏳</span>
          <span className="sensor-label">PLC Busy</span>
          <span className="sensor-value">{plc?.plc_busy ? "ĐANG XỬ LÝ" : "SẴN SÀNG"}</span>
        </div>

        <div className={`sensor-item ${plc?.plc_error ? "active-red" : "inactive"}`}>
          <span className="sensor-icon">❌</span>
          <span className="sensor-label">PLC Error</span>
          <span className="sensor-value">{plc?.plc_error ? "LỖI" : "BÌNH THƯỜNG"}</span>
        </div>
      </div>

      {/* Z-Axis status indicator */}
      <div className="plc-z-axis-status">
        <span className="font-bold">Trục Z:</span>{" "}
        <span className={`status-badge ${
          plc?.z_axis === "UP" ? "status-online" :
          plc?.z_axis === "DOWN" ? "status-busy" :
          plc?.z_axis === "MOVING" ? "status-busy" :
          "status-offline"
        }`}>
          {plc?.z_axis === "UP" ? "⬆️ UP" :
           plc?.z_axis === "DOWN" ? "⬇️ DOWN" :
           plc?.z_axis === "MOVING" ? "🔄 MOVING" :
           "🏠 HOME"}
        </span>
      </div>

      {/* Manual Controls */}
      <div className="plc-action-buttons">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => handleHatch(true)}
          disabled={loading || plc?.plc_busy || !plc?.connected}
        >
          📂 Mở nắp Docking
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => handleHatch(false)}
          disabled={loading || plc?.plc_busy || !plc?.connected}
        >
          📁 Đóng nắp Docking
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => handleLock(true)}
          disabled={loading || plc?.plc_busy || !plc?.connected}
        >
          🔒 Khóa Cố định Drone
        </button>
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => handleLock(false)}
          disabled={loading || plc?.plc_busy || !plc?.connected}
        >
          🔓 Mở khóa Drone
        </button>
      </div>

      {msg && <div className="panel-msg">{msg}</div>}
    </div>
  );
}
