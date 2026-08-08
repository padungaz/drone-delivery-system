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
import { startIntralogisticsMission, pauseMission, resumeMission, overrideMissionQR } from "../services/api";

interface Props {
  devices: DeviceInfo[];
  plc: PLCState | null;
  robot: RobotState | null;
  storage: StorageSlot[];
  activeMission: IntralogisticsMission | null;
  cameraActive?: boolean;
}

export function IntralogisticsPanel({
  devices,
  plc,
  robot,
  storage,
  activeMission,
  cameraActive,
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
      if (!res.ok) {
        const errText = await res.text();
        setMsg(`Lỗi ${res.status}: ${errText}`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || `Khởi tạo nhiệm vụ FSM ${missionType} thành công!`);
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePauseMission = async () => {
    setLoading(true);
    try {
      const res = await pauseMission();
      const data = await res.json();
      setMsg(data.message || "Đã tạm dừng nhiệm vụ");
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleResumeMission = async () => {
    setLoading(true);
    try {
      const res = await resumeMission();
      const data = await res.json();
      setMsg(data.message || "Đã tiếp tục nhiệm vụ");
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleOverrideQR = async () => {
    const inputProduct = prompt("Nhập mã Sản phẩm QR thủ công:", productId);
    if (!inputProduct) return;
    setLoading(true);
    try {
      const res = await overrideMissionQR(inputProduct.trim());
      const data = await res.json();
      setMsg(data.message || "Đã nhập QR thủ công");
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  // Dynamic steps definition for DRONE_PICKUP (Nhập kho) vs DRONE_DELIVERY (Xuất kho)
  const currentType = activeMission?.mission_type ?? missionType;

  const pickupSteps = [
    { key: "STARTED", label: "1. UAV Đáp Pad (Camera OFF)" },
    { key: "DOCK_LOCKED", label: "2. PLC Khóa Drone & Nâng Z" },
    { key: "ROBOT_PICKING", label: "3. Robot gắp SP từ UAV & Hạ Z" },
    { key: "STORAGE_PLACED", label: "4. Quét QR & Cất vào ô kho" },
    { key: "COMPLETED", label: "5. PLC Mở khóa Drone" },
  ];

  const deliverySteps = [
    { key: "STARTED", label: "1. Yêu cầu xuất kho & PLC Khóa" },
    { key: "DOCK_LOCKED", label: "2. Robot lấy hàng từ ô kho" },
    { key: "ROBOT_PICKING", label: "3. Quét QR & PLC Nâng Z" },
    { key: "STORAGE_PLACED", label: "4. Robot đặt SP lên UAV & Hạ Z" },
    { key: "COMPLETED", label: "5. PLC Mở khóa Drone" },
  ];

  const steps = currentType === "DRONE_DELIVERY" ? deliverySteps : pickupSteps;

  // Check for error/cancelled states not in the normal step flow
  const missionState = activeMission?.state ?? "";
  const isErrorState = missionState === "ERROR" || missionState === "CANCELLED" || missionState === "FAILED" || missionState === "REJECTED_LOCATION" || missionState.startsWith("ERROR_");

  return (
    <div className="intralogistics-container">
      {/* Active FSM Mission Tracker Header Banner */}
      <div className="panel fsm-banner">
        <div className="panel-header-inline">
          <h3>🎮 Bộ điều phối Tự động Smart Intralogistics (FSM Orchestrator)</h3>
          {activeMission ? (
            <span className={`badge ${isErrorState ? "error" : "online"} animate-pulse`}>
              {isErrorState ? "🛑" : "🔄"} Nhiệm vụ #{activeMission.id} [{activeMission.mission_type}] — {missionState}
            </span>
          ) : (
            <span className="badge offline">Hệ thống Rảnh (IDLE)</span>
          )}
        </div>

        {/* Error/Cancelled State Banner */}
        {isErrorState && activeMission && (
          <div className="error-banner" style={{ margin: "0.5rem 0", padding: "0.5rem 1rem", borderRadius: "6px", background: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.4)" }}>
            🛡️ Khóa An Toàn / Dừng Nhiệm vụ #{activeMission.id} ở trạng thái <strong>{missionState}</strong>.
            <br />
            <span>Chi tiết: {activeMission.step_details || "Không rõ nguyên nhân"}</span>
          </div>
        )}

        {/* FSM Stepper Progress Bar */}
        <div className="fsm-stepper">
          {steps.map((s, idx) => {
            const isCompletedMission = activeMission?.state === "COMPLETED";
            const stepIdx = steps.findIndex((st) => st.key === activeMission?.state);
            const isPassed = isCompletedMission || (Boolean(activeMission) && stepIdx > idx);
            const isActive = !isCompletedMission && activeMission?.state === s.key;

            return (
              <div
                key={s.key}
                className={`step-item ${isActive ? "active" : ""} ${
                  isPassed ? "completed" : ""
                } ${isErrorState && activeMission ? "error-state" : ""}`}
              >
                <div className="step-number">{idx + 1}</div>
                <div className="step-label">{s.label}</div>
              </div>
            );
          })}
        </div>

        {/* Active step details & Manual Operator Control Toolbar */}
        {activeMission && (
          <div className="step-details-box mt-1" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.9rem", color: "var(--text-secondary, #94a3b8)", background: "rgba(0,0,0,0.2)", padding: "8px 12px", borderRadius: "6px" }}>
            <div>
              📍 Tiến trình chi tiết: <strong style={{ color: "#38bdf8" }}>{activeMission.step_details || activeMission.state}</strong>
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              {activeMission.state === "PAUSED" ? (
                <button type="button" className="btn btn-success btn-sm" onClick={handleResumeMission} disabled={loading}>
                  ▶️ TIẾP TỤC
                </button>
              ) : (
                <button type="button" className="btn btn-warning btn-sm" onClick={handlePauseMission} disabled={loading || isErrorState}>
                  ⏸️ TẠM DỪNG
                </button>
              )}
              <button type="button" className="btn btn-outline btn-sm" onClick={handleOverrideQR} disabled={loading}>
                ✏️ NHẬP QR THỦ CÔNG
              </button>
            </div>
          </div>
        )}

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
          <StorageSlotsGrid slots={storage} externalCameraActive={cameraActive} />
        </div>
      </div>
    </div>
  );
}
