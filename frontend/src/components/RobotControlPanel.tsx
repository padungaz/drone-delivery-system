import { useState } from "react";
import type { RobotState } from "../types/drone";
import { executeRobotPick, executeRobotPlace, robotEmergencyStop } from "../services/api";

interface Props {
  robot: RobotState | null;
}

export function RobotControlPanel({ robot }: Props) {
  const [targetSlot, setTargetSlot] = useState("A1");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const handlePick = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await executeRobotPick(targetSlot);
      const data = await res.json();
      setMsg(data.message || `Đã phát lệnh Robot Pick -> Ô ${targetSlot}`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePlace = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await executeRobotPlace(targetSlot);
      const data = await res.json();
      setMsg(data.message || `Đã phát lệnh Robot Place từ Ô ${targetSlot} -> Docking`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleEStop = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await robotEmergencyStop();
      const data = await res.json();
      setMsg(data.message || "ĐÃ KÍCH HOẠT DỪNG KHẨN CẤP ROBOT!");
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const statusClass =
    robot?.status === "IDLE"
      ? "status-online"
      : robot?.status === "BUSY"
      ? "status-busy"
      : "status-offline";

  return (
    <div className="panel robot-panel">
      <div className="panel-header-inline">
        <h3>🤖 Robot FAIRINO Manipulator</h3>
        <span className={`status-badge ${statusClass}`}>
          {robot?.status ?? "OFFLINE"}
        </span>
      </div>

      <div className="robot-info-grid">
        <div>
          <span className="label font-bold">Tác vụ hiện tại:</span>{" "}
          <span>{robot?.current_task || "Không có (Sẵn sàng)"}</span>
        </div>
        <div>
          <span className="label font-bold">Chế độ hoạt động:</span>{" "}
          <span>{robot?.auto_mode ? "TỰ ĐỘNG (AUTO)" : "THỦ CÔNG (MANUAL)"}</span>
        </div>
      </div>

      {/* Position Monitor */}
      <div className="pos-monitor">
        <h4>Tọa độ Cartesian (mm / deg)</h4>
        <div className="pos-coords">
          <span>X: {robot?.cartesian_position?.x?.toFixed(1) ?? "0.0"}</span>
          <span>Y: {robot?.cartesian_position?.y?.toFixed(1) ?? "0.0"}</span>
          <span>Z: {robot?.cartesian_position?.z?.toFixed(1) ?? "0.0"}</span>
          <span>Rx: {robot?.cartesian_position?.rx?.toFixed(1) ?? "0.0"}°</span>
          <span>Ry: {robot?.cartesian_position?.ry?.toFixed(1) ?? "0.0"}°</span>
          <span>Rz: {robot?.cartesian_position?.rz?.toFixed(1) ?? "0.0"}°</span>
        </div>
      </div>

      {/* Joint Monitor */}
      <div className="pos-monitor">
        <h4>Góc Các Khớp Joint ($J_1 \dots J_6$)</h4>
        <div className="joint-coords">
          {robot?.joint_positions?.map((j, idx) => (
            <span key={`j-${idx + 1}`}>
              J{idx + 1}: {j.toFixed(1)}°
            </span>
          )) ?? <span>Chưa có dữ liệu joint</span>}
        </div>
      </div>

      {/* Robot Manual Actions */}
      <div className="robot-action-box">
        <div className="form-group-inline">
          <label htmlFor="slot-select" className="font-bold">Chọn Ô Kho:</label>
          <select
            id="slot-select"
            className="form-control"
            value={targetSlot}
            onChange={(e) => setTargetSlot(e.target.value)}
          >
            {["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"].map((s) => (
              <option key={s} value={s}>
                Ô {s}
              </option>
            ))}
          </select>
        </div>

        <div className="robot-btn-group">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handlePick}
            disabled={loading || robot?.status === "BUSY"}
          >
            📦 Gắp từ Docking $\rightarrow$ Ô {targetSlot}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handlePlace}
            disabled={loading || robot?.status === "BUSY"}
          >
            📤 Lấy từ Ô {targetSlot} $\rightarrow$ Docking
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={handleEStop}
            disabled={loading}
          >
            🛑 Dừng Khẩn Cấp (E-Stop)
          </button>
        </div>
      </div>

      {msg && <div className="panel-msg">{msg}</div>}
    </div>
  );
}
