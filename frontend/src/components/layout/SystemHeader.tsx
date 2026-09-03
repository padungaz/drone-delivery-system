import { useState, useEffect } from "react";

interface Props {
  sysWsConnected?: boolean;
  uavOnline?: boolean;
  plcOnline?: boolean;
  robotOnline?: boolean;
  cameraOnline?: boolean;
  systemMode?: "AUTO" | "MANUAL";
  autoState?: "STANDBY" | "RUNNING" | "PAUSED" | "ERROR";
  operationMode?: "STATION_AUTO" | "STAFF_OPERATION";
  isStaffRunning?: boolean;
  isLoadingAuto?: boolean;
  onModeToggle?: (mode: "AUTO" | "MANUAL") => void;
  onStartAuto?: () => void;
  onPauseAuto?: () => void;
  onOperationModeToggle?: () => void;
  onResetTasks?: () => void;
  isResettingTasks?: boolean;
  onEStopClick: () => void;
}

export function SystemHeader({
  sysWsConnected = true,
  uavOnline = true,
  plcOnline = true,
  robotOnline = true,
  cameraOnline = true,
  systemMode = "AUTO",
  autoState = "STANDBY",
  operationMode = "STATION_AUTO",
  isStaffRunning = false,
  isLoadingAuto = false,
  isResettingTasks = false,
  onModeToggle,
  onStartAuto,
  onPauseAuto,
  onOperationModeToggle,
  onResetTasks,
  onEStopClick,
}: Props) {
  const [timeStr, setTimeStr] = useState("");
  const [dateStr, setDateStr] = useState("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString("vi-VN", { hour12: false }));
      setDateStr(now.toLocaleDateString("vi-VN"));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleMode = () => {
    const targetMode = systemMode === "AUTO" ? "MANUAL" : "AUTO";
    if (onModeToggle) {
      onModeToggle(targetMode);
    }
  };

  return (
    <header className="hmi-header">
      <div className="hmi-brand">
        <div className="hmi-logo-icon">🤖</div>
        <div className="hmi-title-group">
          <h2>SMART INTRALOGISTICS</h2>
          <span className="hmi-subtitle">FAIRINO FR3 COBOT CELL</span>
        </div>
      </div>

      <div className="hmi-status-bar">
        <div className="hmi-status-pill">
          <span className={`status-dot ${sysWsConnected ? "online" : "offline"}`}></span>
          <span className="pill-label">WS SYSTEM</span>
          <span className="pill-value">{sysWsConnected ? "ONLINE" : "OFFLINE"}</span>
        </div>

        <div className="hmi-status-pill">
          <span className={`status-dot ${uavOnline ? "online" : "offline"}`}></span>
          <span className="pill-label">UAV</span>
          <span className="pill-value">{uavOnline ? "ONLINE" : "OFFLINE"}</span>
        </div>

        <div className="hmi-status-pill">
          <span className={`status-dot ${plcOnline ? "online" : "offline"}`}></span>
          <span className="pill-label">PLC S7-1200</span>
          <span className="pill-value">{plcOnline ? "ONLINE" : "OFFLINE"}</span>
        </div>

        <div className="hmi-status-pill">
          <span className={`status-dot ${robotOnline ? "online" : "offline"}`}></span>
          <span className="pill-label">ROBOT FR3</span>
          <span className="pill-value">{robotOnline ? "ONLINE" : "OFFLINE"}</span>
        </div>

        <div className="hmi-status-pill">
          <span className={`status-dot ${cameraOnline ? "online" : "offline"}`}></span>
          <span className="pill-label">CAMERA</span>
          <span className="pill-value">{cameraOnline ? "ONLINE" : "OFFLINE"}</span>
        </div>
      </div>

      <div className="hmi-header-right">
        {/* System Global AUTO / MANUAL Mode Switch */}
        <div className="system-mode-switch-box">
          <button
            type="button"
            className={`btn-system-mode-toggle ${systemMode === "AUTO" ? "mode-auto" : "mode-manual"}`}
            onClick={handleToggleMode}
            title={
              systemMode === "AUTO"
                ? "Đang ở chế độ AUTO: Bấm để chuyển MANUAL (Thủ công)"
                : "Đang ở chế độ MANUAL: Bấm để chuyển AUTO (Tự động)"
            }
          >
            <span className="mode-icon">{systemMode === "AUTO" ? "⚡" : "🛠️"}</span>
            <div className="mode-text-group">
              <span className="mode-label">CHẾ ĐỘ HỆ THỐNG</span>
              <strong className="mode-value">{systemMode === "AUTO" ? "🤖 AUTO (TỰ ĐỘNG)" : "🎮 MANUAL (THỦ CÔNG)"}</strong>
            </div>
          </button>
        </div>

        {/* Operation Mode Quick Toggle (Kho Trạm Auto vs Nhân viên kho) */}
        <div className="system-op-mode-switch-box">
          <button
            type="button"
            className={`btn-system-mode-toggle ${operationMode === "STAFF_OPERATION" ? "mode-staff-active" : "mode-station-active"}`}
            onClick={onOperationModeToggle}
            title={
              operationMode === "STAFF_OPERATION"
                ? "Đang ở Phân hệ Nhân viên kho. Bấm để trả về Kho Trạm Tự Động (Drone)."
                : "Bấm để kích hoạt Phân hệ Nhân viên kho (xuất/nạp băng tải)."
            }
          >
            <span className="mode-icon">{operationMode === "STAFF_OPERATION" ? "👨‍💼" : "🚁"}</span>
            <div className="mode-text-group">
              <span className="mode-label">PHÂN HỆ VẬN HÀNH</span>
              <strong className="mode-value">
                {operationMode === "STAFF_OPERATION" ? "NHÂN VIÊN KHO" : "KHO TRẠM AUTO"}
              </strong>
            </div>
          </button>
        </div>

        {/* Station AUTO Start / Pause Master Control */}
        <div className="system-auto-control-box">
          {systemMode === "MANUAL" ? (
            <button
              type="button"
              className="btn-auto-action mode-disabled"
              disabled
              title="Chuyển sang chế độ AUTO để khởi động tự động toàn bộ kho trạm"
            >
              <span className="action-icon">🔒</span>
              <div className="action-text-group">
                <span className="action-label">KHO TRẠM</span>
                <strong className="action-value">KHÓA TỰ ĐỘNG</strong>
              </div>
            </button>
          ) : isStaffRunning ? (
            <div className="auto-running-controls">
              <div className="auto-running-badge staff-running-badge" title="Nhân viên kho đang xuất hoặc nhập hàng qua băng tải">
                <span className="pulse-dot"></span>
                <span className="running-text">👨‍💼 NHÂN VIÊN ĐANG CHẠY</span>
              </div>
            </div>
          ) : autoState === "RUNNING" ? (
            <div className="auto-running-controls">
              <div className="auto-running-badge">
                <span className="pulse-dot"></span>
                <span className="running-text">AUTO RUNNING</span>
              </div>
              <button
                type="button"
                className="btn-auto-action action-pause"
                onClick={onPauseAuto}
                title="Tạm dừng xử lý hàng đợi tự động"
              >
                <span className="action-icon">⏸️</span>
                <span className="action-text">TẠM DỪNG</span>
              </button>
            </div>
          ) : (
            <button
              type="button"
              className={`btn-auto-action action-start pulse-start ${isLoadingAuto ? "loading" : ""}`}
              onClick={onStartAuto}
              disabled={isLoadingAuto}
              title={
                operationMode === "STAFF_OPERATION"
                  ? "Bấm để kích hoạt Chế độ Kho Trạm (Drone) và chạy tự động hàng đợi FIFO"
                  : "Kiểm tra tiền khởi động, đưa Robot về Home & chạy hàng đợi FIFO"
              }
            >
              <span className="action-icon">{isLoadingAuto ? "⏳" : "▶️"}</span>
              <div className="action-text-group">
                <span className="action-label">KHO TRẠM</span>
                <strong className="action-value">
                  {isLoadingAuto
                    ? "ĐANG KHỞI ĐỘNG..."
                    : autoState === "PAUSED"
                    ? "TIẾP TỤC CHẠY"
                    : "START KHO TRẠM"}
                </strong>
              </div>
            </button>
          )}
        </div>

        {/* Master Task Reset Button */}
        <button
          type="button"
          className={`btn-system-reset ${isResettingTasks ? "loading" : ""}`}
          onClick={onResetTasks}
          disabled={isResettingTasks}
          title="Hủy bỏ các đơn đang chạy dở và đưa trạm về trạng thái Chờ (IDLE)"
        >
          <span className="reset-icon">{isResettingTasks ? "⏳" : "🔄"}</span>
          <div className="reset-text-group">
            <span className="reset-label">HỆ THỐNG</span>
            <strong className="reset-value">{isResettingTasks ? "ĐANG RESET..." : "RESET TÁC VỤ"}</strong>
          </div>
        </button>

        <div className="hmi-clock-box">
          <span className="hmi-time">{timeStr || "21:17:46"}</span>
          <span className="hmi-date">{dateStr || "16/08/2026"}</span>
        </div>

        <button type="button" className="estop-button" onClick={onEStopClick}>
          <span className="estop-icon">🛑</span>
          <div className="estop-text">
            <strong>E-STOP</strong>
            <small>EMERGENCY STOP</small>
          </div>
        </button>
      </div>
    </header>
  );
}

