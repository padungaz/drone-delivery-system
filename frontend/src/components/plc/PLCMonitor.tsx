import React, { useState } from "react";
import {
  controlPlcLock,
  controlPlcZLevel,
  setSimulatedDroneSensor,
  setSimulatedEmergencyStop,
  startPlc,
  stopPlc,
  resetPlc,
  executePlcCommand,
} from "../../services/api";

interface Props {
  connected?: boolean;
  ipAddress?: string;
  rackSlot?: string;
  cycleTimeMs?: number;
  db15Status?: string;
  droneDetected?: boolean;
  lockClamp?: boolean;
  eStopOk?: boolean;
  systemMode?: "AUTO" | "MANUAL";
  watchdogActive?: boolean;
  zAxis?: string;
  currentZLevel?: number;
  targetZLevel?: number;
  zInPosition?: boolean;
  cmdTargetZ?: boolean;
  isRobotBusy?: boolean;
}

const Z_LEVEL_NAMES: Record<number, string> = {
  0: "HOME (0)",
  1: "TẦNG A (1)",
  2: "TẦNG B (2)",
  3: "DRONE N1 (3)",
  4: "BĂNG TẢI O1 (4)",
};

export const PLCMonitor = React.memo(function PLCMonitor({
  connected = true,
  ipAddress = "192.168.58.10",
  rackSlot = "0 / 1",
  cycleTimeMs = 12,
  db15Status = "READING (DB15)",
  droneDetected = true,
  lockClamp = true,
  eStopOk = true,
  systemMode = "AUTO",
  watchdogActive = false,
  zAxis = "DOWN",
  currentZLevel = 0,
  targetZLevel = 0,
  zInPosition = true,
  cmdTargetZ = false,
  isRobotBusy = false,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const isActionDisabled = loading || isRobotBusy;

  const handleCommand = async (action: () => Promise<Response>, successMsg: string) => {
    if (isRobotBusy) {
      setFeedback("⚠️ Robot đang hoạt động! Toàn bộ thao tác PLC bị khóa để đảm bảo an toàn.");
      return;
    }
    setLoading(true);
    setFeedback(null);
    try {
      const res = await action();
      if (res.ok) {
        setFeedback(`✅ ${successMsg}`);
      } else {
        const err = await res.json().catch(() => ({}));
        setFeedback(`❌ Lỗi: ${err.detail || "Thao tác thất bại"}`);
      }
    } catch {
      setFeedback("❌ Lỗi kết nối tới PLC API");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="hmi-card plc-monitor-card">
      <div className="card-header flex-between">
        <div className="card-title-group">
          <h3>⚙️ PLC S7-1200 STATUS</h3>
          <span className="card-subtitle">SIEMENS PROFINET / SNAP7 HARDWARE</span>
        </div>
        <span className={`connection-badge ${connected ? "online" : "offline"}`}>
          {connected ? "ONLINE ●" : "OFFLINE ●"}
        </span>
      </div>

      <div className="card-body plc-layout">
        <div className="plc-hardware-visual">
          {/* Detailed Siemens S7-1200 Industrial CPU SVG Graphic */}
          <div className="plc-device-graphic">
            <div className="plc-brand-banner">
              <span className="siemens-brand">SIEMENS</span>
              <span className="plc-model font-mono">SIMATIC S7-1200</span>
            </div>
            <div className="plc-cpu-body">
              <div className="cpu-door">
                <div className="led-row">
                  <div className="led-item"><span className="led led-run active"></span> RUN/STOP</div>
                  <div className="led-item"><span className="led led-error"></span> ERROR</div>
                  <div className="led-item"><span className="led led-maint"></span> MAINT</div>
                </div>
              </div>
              <div className="io-terminal-strip">
                <span className="term-pin active"></span>
                <span className="term-pin active"></span>
                <span className="term-pin active"></span>
                <span className="term-pin"></span>
                <span className="term-pin active"></span>
              </div>
            </div>
          </div>

          <div className="plc-specs-list">
            <div className="spec-row flex-between">
              <span>Connection</span>
              <strong className="text-green">{connected ? "ONLINE (PROFINET)" : "OFFLINE"}</strong>
            </div>
            <div className="spec-row flex-between">
              <span>IP Address</span>
              <strong className="font-mono text-cyan">{ipAddress}</strong>
            </div>
            <div className="spec-row flex-between">
              <span>Rack / Slot</span>
              <strong className="font-mono">{rackSlot}</strong>
            </div>
            <div className="spec-row flex-between">
              <span>Cycle Time</span>
              <strong className="font-mono">{cycleTimeMs} ms</strong>
            </div>
            <div className="spec-row flex-between">
              <span>DB15 Status</span>
              <strong className="text-cyan font-mono">{db15Status}</strong>
            </div>
            <div className="spec-row flex-between">
              <span>Tầng Trục Z (DBW8)</span>
              <strong className="text-cyan font-mono">
                {Z_LEVEL_NAMES[currentZLevel] || `LEVEL ${currentZLevel}`}
                {targetZLevel !== 0 && targetZLevel !== currentZLevel ? ` → Mục tiêu: ${Z_LEVEL_NAMES[targetZLevel] || targetZLevel}` : ""}
                {zInPosition ? " (SẴN SÀNG)" : " (ĐANG DI CHUYỂN)"}
              </strong>
            </div>
          </div>
        </div>

        {/* Symmetrical 6-Box PLC Status Indicators Grid */}
        <div className="plc-db15-indicators">
          {/* 1. Drone Detect */}
          <div className={`indicator-box ${droneDetected ? "active" : ""}`} title="Cảm biến phát hiện Drone hạ cánh tại Dock N1 (DB15.DBX2.0)">
            <span className="icon">🚁</span>
            <span className="label">Drone Detect</span>
            <span className="value font-mono">{droneDetected ? "CÓ DRONE (DB2.0)" : "TRỐNG"}</span>
          </div>

          {/* 2. Lock Clamp */}
          <div className={`indicator-box ${lockClamp ? "active-ok" : ""}`} title="Cơ cấu ngàm khóa Drone (DB15.DBX2.1)">
            <span className="icon">🔒</span>
            <span className="label">Lock Clamp</span>
            <span className="value font-mono">{lockClamp ? "LOCKED (DB2.1)" : "OPEN (MỞ)"}</span>
          </div>

          {/* 3. Z-Level (DBW8) */}
          <div className="indicator-box active-ok" title="Tầng trục Z hiện tại (DB15.DBW8)">
            <span className="icon">📐</span>
            <span className="label">Z-Level (DBW8)</span>
            <span className="value font-mono">{Z_LEVEL_NAMES[currentZLevel] || `LEVEL ${currentZLevel}`}</span>
          </div>

          {/* 4. Z In Position (DB2.7) & Trigger (DB0.2) */}
          <div className={`indicator-box ${zInPosition ? "active" : "active-warn"}`} title="Cờ xác nhận trục Z đã đến tầng (DB15.DBX2.7). Lệnh kích hoạt DB15.DBX0.2 (cmd_target_z)">
            <span className="icon">{zInPosition ? "🎯" : "🔄"}</span>
            <span className="label">Vị Trí Z (DB2.7)</span>
            <span className="value font-mono">
              {zInPosition ? "● SẴN SÀNG" : cmdTargetZ ? "🚀 LỆNH DB0.2" : "🔄 ĐANG CHẠY"}
            </span>
          </div>

          {/* 5. E-Stop Status (DB2.6) */}
          <div className={`indicator-box ${zAxis === "MOVING" ? "active-warn" : eStopOk ? "active-ok" : "active-error"}`} title="Trạng thái nút dừng khẩn cấp E-Stop (DB15.DBX2.6)">
            <span className="icon">🛑</span>
            <span className="label">E-Stop Status</span>
            <span className="value font-mono">{eStopOk ? "OK (DB2.6)" : "KÍCH HOẠT"}</span>
          </div>

          {/* 6. Watchdog Heartbeat (DB0.7) */}
          <div className={`indicator-box ${watchdogActive ? "active" : "inactive"}`} title="PLC Watchdog Heartbeat (DB15.DBX0.7) — Toggle mỗi 1s khi kết nối thật">
            <span className="icon">{watchdogActive ? "⚡" : "💤"}</span>
            <span className="label">Watchdog (DB0.7)</span>
            <span className="value font-mono">{watchdogActive ? "ACTIVE (1s)" : "DISABLED"}</span>
          </div>
        </div>

        {/* Manual Direct Hardware Controls Toolbar - ONLY VISIBLE IN MANUAL MODE */}
        {systemMode === "MANUAL" && (
          <div className="plc-manual-controls-section">
            <div className="manual-section-title">
              <span className="font-mono text-cyan">🎮 ĐIỀU KHIỂN THỦ CÔNG PLC (MANUAL OVERRIDE):</span>
              {isRobotBusy ? (
                <span
                  className="mode-indicator-tag active-warn"
                  style={{ background: "#f59e0b", color: "#000", fontWeight: "bold", padding: "2px 8px", borderRadius: "4px" }}
                >
                  ⚠️ ROBOT ĐANG CHẠY — ĐÃ KHÓA PLC
                </span>
              ) : (
                <span className="mode-indicator-tag active-manual">MANUAL SẴN SÀNG</span>
              )}
            </div>

            {/* Safety Interlock Banner when Robot is Running */}
            {isRobotBusy && (
              <div
                style={{
                  margin: "6px 0 10px 0",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  background: "rgba(239, 68, 68, 0.15)",
                  border: "1px solid rgba(239, 68, 68, 0.5)",
                  color: "#f87171",
                  fontSize: "12px",
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <span>🛑</span>
                <span>Robot đang vận hành / chuyển động! Toàn bộ thao tác PLC bị khóa để chống va chạm cơ khí.</span>
              </div>
            )}

            {feedback && <div className="manual-feedback-pill font-mono">{feedback}</div>}

            {/* Group 1: Multi-Level Z Control (DB15.DBW8) */}
            <div className="manual-control-group">
              <div className="manual-group-label">
                <span>📐 ĐIỀU KHIỂN TẦNG TRỤC Z (DB15.DBW8):</span>
              </div>
              <div className="manual-btn-grid-5">
                <button
                  type="button"
                  className={`btn-manual-plc ${currentZLevel === 0 ? "active-level" : ""}`}
                  onClick={() => handleCommand(() => controlPlcZLevel(0), "PLC Trục Z: Về HOME (Mã 0)")}
                  disabled={isActionDisabled}
                  title="Di chuyển trục Z về vị trí HOME gốc"
                >
                  🏠 Home (0)
                </button>
                <button
                  type="button"
                  className={`btn-manual-plc ${currentZLevel === 1 ? "active-level" : ""}`}
                  onClick={() => handleCommand(() => controlPlcZLevel(1), "PLC Trục Z: Đến HÀNG A (Mã 1)")}
                  disabled={isActionDisabled}
                  title="Nâng trục Z lên độ cao HÀNG A (A1..A3)"
                >
                  📦 Tầng A (1)
                </button>
                <button
                  type="button"
                  className={`btn-manual-plc ${currentZLevel === 2 ? "active-level" : ""}`}
                  onClick={() => handleCommand(() => controlPlcZLevel(2), "PLC Trục Z: Đến HÀNG B (Mã 2)")}
                  disabled={isActionDisabled}
                  title="Nâng trục Z lên độ cao HÀNG B (B1..B3)"
                >
                  📦 Tầng B (2)
                </button>
                <button
                  type="button"
                  className={`btn-manual-plc ${currentZLevel === 3 ? "active-level" : ""}`}
                  onClick={() => handleCommand(() => controlPlcZLevel(3), "PLC Trục Z: Đến DRONE N1 (Mã 3)")}
                  disabled={isActionDisabled}
                  title="Nâng trục Z lên độ cao bãi đáp Drone N1"
                >
                  🚁 Drone N1 (3)
                </button>
                <button
                  type="button"
                  className={`btn-manual-plc ${currentZLevel === 4 ? "active-level" : ""}`}
                  onClick={() => handleCommand(() => controlPlcZLevel(4), "PLC Trục Z: Đến BĂNG TẢI O1 (Mã 4)")}
                  disabled={isActionDisabled}
                  title="Hạ trục Z xuống vị trí băng tải O1"
                >
                  🛞 Băng Tải O1 (4)
                </button>
              </div>
            </div>

            {/* Group 2: Drone Lock (Dock N1) */}
            <div className="manual-control-group">
              <div className="manual-group-label">
                <span>🚁 CƠ CẤU NGÀM KHÓA DRONE (DOCK N1 - DB15 BYTE 0):</span>
              </div>
              <div className="manual-btn-grid-2">
                <button
                  type="button"
                  className={`btn-manual-plc ${lockClamp ? "active-status" : ""}`}
                  onClick={() => handleCommand(() => controlPlcLock(true), "Đã kích hoạt khóa Drone (LOCK)")}
                  disabled={isActionDisabled}
                  title="Khóa kẹp cơ khí cố định Drone (DB15.DBX0.0)"
                >
                  🔒 Khóa Drone
                </button>
                <button
                  type="button"
                  className={`btn-manual-plc ${!lockClamp ? "active-status" : ""}`}
                  onClick={() => handleCommand(() => controlPlcLock(false), "Đã mở khóa Drone (UNLOCK)")}
                  disabled={isActionDisabled}
                  title="Mở khóa giải phóng Drone (DB15.DBX0.1)"
                >
                  🔓 Mở Khóa Drone
                </button>
              </div>
            </div>

            {/* Group 3: PLC Main Power & Control (Byte 0) */}
            <div className="manual-control-group">
              <div className="manual-group-label">
                <span>⚡ ĐIỀU HÀNH CHÍNH PLC (DB15 BYTE 0):</span>
              </div>
              <div className="manual-btn-grid-3">
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-green"
                  onClick={() => handleCommand(startPlc, "Đã khởi động PLC (START_PLC)")}
                  disabled={isActionDisabled}
                  title="Bật / Kích hoạt hệ thống PLC (DB15.DBX0.5)"
                >
                  ▶️ Start PLC
                </button>
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-red"
                  onClick={() => handleCommand(stopPlc, "Đã dừng PLC (STOP_PLC)")}
                  disabled={isActionDisabled}
                  title="Dừng hệ thống PLC (DB15.DBX0.4)"
                >
                  ⏹ Stop PLC
                </button>
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-yellow"
                  onClick={() => handleCommand(resetPlc, "Đã reset lỗi PLC (RESET_PLC)")}
                  disabled={isActionDisabled}
                  title="Reset cờ báo lỗi PLC (DB15.DBX0.6)"
                >
                  🔄 Reset Lỗi
                </button>
              </div>
            </div>

            {/* Group 4: Staff Mode Commands (Byte 1) */}
            <div className="manual-control-group">
              <div className="manual-group-label">
                <span>👷 CHẾ ĐỘ NHÂN VIÊN & BĂNG TẢI (DB15 BYTE 1):</span>
              </div>
              <div className="manual-btn-grid-4">
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-cyan"
                  onClick={() => handleCommand(() => executePlcCommand("STAFF_MODE_ENABLE"), "Đã bật Chế độ Nhân viên (STAFF_MODE_ENABLE)")}
                  disabled={isActionDisabled}
                  title="Kích hoạt Staff Mode (DB15.DBX1.0 = 1)"
                >
                  👷 Bật Staff Mode
                </button>
                <button
                  type="button"
                  className="btn-manual-plc"
                  onClick={() => handleCommand(() => executePlcCommand("STAFF_MODE_DISABLE"), "Đã tắt Chế độ Nhân viên (STAFF_MODE_DISABLE)")}
                  disabled={isActionDisabled}
                  title="Tắt Staff Mode, quay về Station Auto (DB15.DBX1.0 = 0)"
                >
                  🛑 Tắt Staff Mode
                </button>
                <button
                  type="button"
                  className="btn-manual-plc"
                  onClick={() => handleCommand(() => executePlcCommand("STAFF_OUTBOUND_START"), "Bắt đầu chu trình xuất hàng ra băng tải")}
                  disabled={isActionDisabled}
                  title="Lệnh bắt đầu xuất hàng ra băng tải (DB15.DBX1.1)"
                >
                  📦 Xuất Ra Băng Tải
                </button>
                <button
                  type="button"
                  className="btn-manual-plc"
                  onClick={() => handleCommand(() => executePlcCommand("STAFF_INBOUND_START"), "Bắt đầu chu trình nhập hàng từ O1")}
                  disabled={isActionDisabled}
                  title="Lệnh bắt đầu nạp hàng từ O1 (DB15.DBX1.3)"
                >
                  📥 Nhập Từ O1
                </button>
              </div>
            </div>

            {/* Group 5: Sensor & Emergency Simulation */}
            <div className="manual-control-group">
              <div className="manual-group-label">
                <span>🧪 MÔ PHỎNG CẢM BIẾN & TÍN HIỆU AN TOÀN:</span>
              </div>
              <div className="manual-sensor-row">
                <span className="lbl-mini">Cảm biến Drone Đáp (DB2.0):</span>
                <div className="sensor-toggle-group">
                  <button
                    type="button"
                    className={`btn-sensor-toggle ${droneDetected ? "active-detected" : ""}`}
                    onClick={() => handleCommand(() => setSimulatedDroneSensor(true), "Cảm biến: CÓ DRONE ĐÁP")}
                    disabled={isActionDisabled}
                  >
                    ● Có Drone
                  </button>
                  <button
                    type="button"
                    className={`btn-sensor-toggle ${!droneDetected ? "active-empty" : ""}`}
                    onClick={() => handleCommand(() => setSimulatedDroneSensor(false), "Cảm biến: BÃI ĐÁP TRỐNG")}
                    disabled={isActionDisabled}
                  >
                    ○ Bãi Trống
                  </button>
                </div>
              </div>

              <div className="manual-sensor-row">
                <span className="lbl-mini">Giả lập E-Stop (DB2.6):</span>
                <div className="sensor-toggle-group">
                  <button
                    type="button"
                    className={`btn-sensor-toggle ${!eStopOk ? "active-estop" : ""}`}
                    onClick={() => handleCommand(() => setSimulatedEmergencyStop(true), "CẢNH BÁO: Kích hoạt E-Stop thủ công!")}
                    disabled={isActionDisabled}
                  >
                    🛑 Kích Hoạt E-Stop
                  </button>
                  <button
                    type="button"
                    className={`btn-sensor-toggle ${eStopOk ? "active-detected" : ""}`}
                    onClick={() => handleCommand(() => setSimulatedEmergencyStop(false), "E-Stop: Đã đưa về Bình thường")}
                    disabled={isActionDisabled}
                  >
                    ✅ E-Stop Bình Thường
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});
