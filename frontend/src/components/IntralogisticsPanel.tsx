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
import { pauseMission, resumeMission, overrideMissionQR, startAutoBatchMissions } from "../services/api";

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
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const handleStartSystem = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await startAutoBatchMissions();
      if (!res.ok) {
        setMsg(`Lỗi ${res.status}: Không thể kích hoạt hệ thống`);
        return;
      }
      const data = await res.json();
      setMsg(data.message || "🚀 Đã bấm START SYSTEM! Backend tự động điều phối các đơn hàng theo thứ tự FIFO.");
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
    const inputProduct = prompt("Nhập mã Sản phẩm QR thủ công:", activeMission?.product_id || "PROD-1001");
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
  const currentType = activeMission?.mission_type ?? "DRONE_PICKUP";

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

        {/* Decoupled Dual Timeline View (Station Process & UAV Mission) */}
        {activeMission && (activeMission.station_process || activeMission.uav_mission) ? (
          <div className="dual-timeline-container" style={{ margin: "1rem 0", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            {/* Station Process Panel */}
            <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "12px", borderRadius: "8px", border: "1px solid rgba(56, 189, 248, 0.3)" }}>
              <h4 style={{ color: "#38bdf8", margin: "0 0 10px 0", fontSize: "0.95rem" }}>
                ⚙️ Trạm Tự Động Mặt Đất (Station Process - PLC + Robot)
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {(activeMission.station_process?.steps || []).map((step) => (
                  <div key={step.step} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", padding: "4px 8px", borderRadius: "4px", background: step.status === "completed" ? "rgba(34, 197, 94, 0.15)" : step.status === "in_progress" ? "rgba(56, 189, 248, 0.2)" : "rgba(255,255,255,0.03)" }}>
                    <span>{step.status === "completed" ? "✅" : step.status === "in_progress" ? "🔄" : "⏳"}</span>
                    <span style={{ fontWeight: 600, color: "#93c5fd", minWidth: "50px" }}>[{step.device}]</span>
                    <span style={{ flex: 1, color: step.status === "in_progress" ? "#38bdf8" : "#cbd5e1" }}>{step.description}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* UAV Mission Panel */}
            <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "12px", borderRadius: "8px", border: "1px solid rgba(168, 85, 247, 0.3)" }}>
              <h4 style={{ color: "#c084fc", margin: "0 0 10px 0", fontSize: "0.95rem" }}>
                🚀 Hàng Không UAV (UAV Mission - Xuất phát từ HOME)
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {(activeMission.uav_mission?.steps || []).map((step) => (
                  <div key={step.step} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", padding: "4px 8px", borderRadius: "4px", background: step.status === "completed" ? "rgba(34, 197, 94, 0.15)" : step.status === "in_progress" ? "rgba(168, 85, 247, 0.2)" : "rgba(255,255,255,0.03)" }}>
                    <span>{step.status === "completed" ? "✅" : step.status === "in_progress" ? "🛸" : "⏳"}</span>
                    <span style={{ fontWeight: 600, color: "#e9d5ff", minWidth: "75px" }}>[{step.action}]</span>
                    <span style={{ flex: 1, color: step.status === "in_progress" ? "#c084fc" : "#cbd5e1" }}>{step.description}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Default FSM Stepper Progress Bar */
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
        )}

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

        {/* System Orchestrator Control Bar */}
        <div className="create-mission-box mt-2" style={{ background: "linear-gradient(135deg, rgba(16,185,129,0.1) 0%, rgba(59,130,246,0.1) 100%)", border: "1px solid rgba(16,185,129,0.3)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h4 style={{ margin: 0, fontSize: "1.1rem", color: "#10b981" }}>🚀 VẬN HÀNH HỆ THỐNG TỰ ĐỘNG (SYSTEM ORCHESTRATOR)</h4>
              <p className="muted" style={{ margin: "0.27rem 0 0 0", fontSize: "0.85rem" }}>
                Backend chịu trách nhiệm điều phối Mission Manager (UAV + PLC + Robot FSM) theo thứ tự FIFO.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-success"
              style={{ padding: "0.75rem 1.75rem", fontSize: "1rem", fontWeight: 800, letterSpacing: "0.5px" }}
              onClick={handleStartSystem}
              disabled={loading || !!activeMission}
            >
              ⚡ START SYSTEM
            </button>
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
