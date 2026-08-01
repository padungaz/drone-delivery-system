import { useState } from "react";
import type { RobotState } from "../types/drone";
import { executeRobotPick, executeRobotPlace, robotEmergencyStop, sendRobotDoneSignal } from "../services/api";

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
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
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
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
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
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || "ĐÃ KÍCH HOẠT DỪNG KHẨN CẤP ROBOT!");
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDoneSignal = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await sendRobotDoneSignal();
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || "✅ Đã giả lập gửi tín hiệu ROBOT_DONE về Backend thành công!");
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

      {/* Robot Manual Actions */}
      <div className="robot-action-box mt-2">
        <div className="form-group-inline">
          <label htmlFor="slot-select" className="font-bold">Chọn Ô Kho Chỉ Định:</label>
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

        <div className="robot-btn-group mt-1">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handlePick}
            disabled={loading || robot?.status === "BUSY"}
          >
            📦 Gắp từ Docking → Ô {targetSlot}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handlePlace}
            disabled={loading || robot?.status === "BUSY"}
          >
            📤 Lấy từ Ô {targetSlot} → Docking
          </button>
          <button
            type="button"
            className="btn btn-success"
            onClick={handleDoneSignal}
            disabled={loading}
            title="Gửi tín hiệu báo Robot đã hoàn thành tác vụ (ROBOT_DONE) về Backend"
          >
            ✅ Giả lập: Tín Hiệu DONE
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

      {msg && <div className="panel-msg mt-1">{msg}</div>}
    </div>
  );
}
