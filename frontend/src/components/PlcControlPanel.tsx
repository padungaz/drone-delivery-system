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
      <h3>⚡ Điều khiển Docking PLC S7-1200</h3>

      {/* Sensor Indicators */}
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
      </div>

      {/* Manual Controls */}
      <div className="plc-action-buttons">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => handleHatch(true)}
          disabled={loading}
        >
          📂 Mở nắp Docking
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => handleHatch(false)}
          disabled={loading}
        >
          📁 Đóng nắp Docking
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => handleLock(true)}
          disabled={loading}
        >
          🔒 Khóa Cố định Drone
        </button>
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => handleLock(false)}
          disabled={loading}
        >
          🔓 Mở khóa Drone
        </button>
      </div>

      {msg && <div className="panel-msg">{msg}</div>}
    </div>
  );
}
