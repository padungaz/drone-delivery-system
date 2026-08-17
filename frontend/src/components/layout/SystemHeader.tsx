import { useState, useEffect } from "react";

interface Props {
  sysWsConnected?: boolean;
  uavOnline?: boolean;
  plcOnline?: boolean;
  robotOnline?: boolean;
  cameraOnline?: boolean;
  systemMode?: "AUTO" | "MANUAL";
  onModeToggle?: (mode: "AUTO" | "MANUAL") => void;
  onEStopClick: () => void;
}

export function SystemHeader({
  sysWsConnected = true,
  uavOnline = true,
  plcOnline = true,
  robotOnline = true,
  cameraOnline = true,
  systemMode = "AUTO",
  onModeToggle,
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
                ? "Đang ở chế độ AUTO: Hệ thống tự động thực thi đơn hàng. Bấm để chuyển MANUAL"
                : "Đang ở chế độ MANUAL: Đơn hàng bị khóa, cho phép thử nghiệm độc lập từng thiết bị. Bấm để chuyển AUTO"
            }
          >
            <span className="mode-icon">{systemMode === "AUTO" ? "⚡" : "🛠️"}</span>
            <div className="mode-text-group">
              <span className="mode-label">CHẾ ĐỘ HỆ THỐNG</span>
              <strong className="mode-value">{systemMode === "AUTO" ? "🤖 AUTO (TỰ ĐỘNG)" : "🎮 MANUAL (THỦ CÔNG)"}</strong>
            </div>
          </button>
        </div>

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
