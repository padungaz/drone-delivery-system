import { useState } from "react";
import type {
  DeviceInfo,
  PLCState,
  RobotState,
  StorageSlot,
  IntralogisticsMission,
} from "../types/drone";
import { DeviceStatusPanel } from "./DeviceStatusPanel";
import { PlcControlPanel } from "./PlcControlPanel";
import { RobotControlPanel } from "./RobotControlPanel";
import { StorageSlotsGrid } from "./StorageSlotsGrid";
import { startIntralogisticsMission } from "../services/api";

interface Props {
  devices: DeviceInfo[];
  plc: PLCState | null;
  robot: RobotState | null;
  storage: StorageSlot[];
  activeMission: IntralogisticsMission | null;
}

export function IntralogisticsPanel({
  devices,
  plc,
  robot,
  storage,
  activeMission,
}: Props) {
  const [missionType, setMissionType] = useState<"DRONE_PICKUP" | "DRONE_DELIVERY">(
    "DRONE_PICKUP"
  );
  const [productId, setProductId] = useState("PROD-1001");
  const [targetSlot, setTargetSlot] = useState("A1");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const handleStartMission = async () => {
    if (!productId.trim()) return;
    setLoading(true);
    setMsg(null);
    try {
      const res = await startIntralogisticsMission(missionType, productId.trim(), targetSlot);
      const data = await res.json();
      setMsg(data.message || `Khởi tạo nhiệm vụ FSM ${missionType} thành công!`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  // Steps definition for FSM progress stepper
  const steps = [
    { key: "STARTED", label: "1. UAV Hạ cánh" },
    { key: "DOCK_LOCKED", label: "2. PLC Khóa Dock & Mở nắp" },
    { key: "ROBOT_PICKING", label: "3. Robot gắp hàng" },
    { key: "STORAGE_PLACED", label: "4. Lưu vị trí ô kho" },
    { key: "COMPLETED", label: "5. PLC Đóng nắp & Hoàn thành" },
  ];

  return (
    <div className="intralogistics-container">
      {/* Active FSM Mission Tracker Header Banner */}
      <div className="panel fsm-banner">
        <div className="panel-header-inline">
          <h3>🎮 Bộ điều phối Tự động Smart Intralogistics (FSM Orchestrator)</h3>
          {activeMission ? (
            <span className="badge online animate-pulse">
              Đang chạy Nhiệm vụ #{activeMission.id} [{activeMission.mission_type}]
            </span>
          ) : (
            <span className="badge offline">Hệ thống Rảnh (IDLE)</span>
          )}
        </div>

        {/* FSM Stepper Progress Bar */}
        <div className="fsm-stepper">
          {steps.map((s, idx) => {
            const isActive = activeMission?.state === s.key;
            const isPassed =
              activeMission &&
              steps.findIndex((st) => st.key === activeMission.state) > idx;

            return (
              <div
                key={s.key}
                className={`step-item ${isActive ? "active" : ""} ${
                  isPassed ? "completed" : ""
                }`}
              >
                <div className="step-number">{idx + 1}</div>
                <div className="step-label">{s.label}</div>
              </div>
            );
          })}
        </div>

        {/* Create Mission Trigger Form */}
        <div className="create-mission-box mt-2">
          <h4>🚀 Tạo Nhiệm vụ Intralogistics Tự động mới:</h4>
          <div className="mission-form-grid">
            <div>
              <label htmlFor="mission-type-select" className="font-bold">Loại Nhiệm vụ:</label>
              <select
                id="mission-type-select"
                className="form-control"
                value={missionType}
                onChange={(e) => setMissionType(e.target.value as "DRONE_PICKUP" | "DRONE_DELIVERY")}
              >
                <option value="DRONE_PICKUP">DRONE_PICKUP (UAV Nhận hàng vào kho)</option>
                <option value="DRONE_DELIVERY">DRONE_DELIVERY (Xuất kho lên UAV giao đi)</option>
              </select>
            </div>

            <div>
              <label htmlFor="prod-id-input" className="font-bold">Mã Hàng hóa (Product ID):</label>
              <input
                id="prod-id-input"
                type="text"
                className="form-control"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                placeholder="PROD-1001"
              />
            </div>

            <div>
              <label htmlFor="target-slot-select" className="font-bold">Ô kho chỉ định (Slot):</label>
              <select
                id="target-slot-select"
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

            <div className="align-end">
              <button
                type="button"
                className="btn btn-primary w-full"
                onClick={handleStartMission}
                disabled={loading || !!activeMission}
              >
                ▶️ KÍCH HOẠT CHUỖI FSM
              </button>
            </div>
          </div>

          {msg && <div className="panel-msg mt-1">{msg}</div>}
        </div>
      </div>

      {/* Main 2-Column Dashboard Layout */}
      <div className="intralogistics-grid mt-2">
        {/* Left Column: Device status + PLC + Robot controls */}
        <div className="grid-column">
          <DeviceStatusPanel devices={devices} />
          <PlcControlPanel plc={plc} />
          <RobotControlPanel robot={robot} />
        </div>

        {/* Right Column: 3x3 Storage slots grid */}
        <div className="grid-column">
          <StorageSlotsGrid slots={storage} />
        </div>
      </div>
    </div>
  );
}
