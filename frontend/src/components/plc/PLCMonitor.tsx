import { useState } from "react";
import {
  controlPlcHatch,
  controlPlcLock,
  setSimulatedDroneSensor,
  startPlc,
  stopPlc,
  resetPlc,
} from "../../services/api";

interface Props {
  connected?: boolean;
  ipAddress?: string;
  rackSlot?: string;
  cycleTimeMs?: number;
  db15Status?: string;
  droneDetected?: boolean;
  lockClamp?: boolean;
  zLiftUp?: boolean;
  zLiftDown?: boolean;
  eStopOk?: boolean;
  systemMode?: "AUTO" | "MANUAL";
}

export function PLCMonitor({
  connected = true,
  ipAddress = "192.168.58.10",
  rackSlot = "0 / 1",
  cycleTimeMs = 12,
  db15Status = "READING (DB15)",
  droneDetected = true,
  lockClamp = true,
  zLiftUp = true,
  eStopOk = true,
  systemMode = "AUTO",
}: Props) {
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleCommand = async (action: () => Promise<Response>, successMsg: string) => {
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
          </div>
        </div>

        <div className="plc-db15-indicators flex-between">
          <div className={`indicator-box ${droneDetected ? "active" : ""}`}>
            <span className="icon">🚁</span>
            <span className="label">Drone Detect</span>
            <span className="value font-mono">{droneDetected ? "ON (DB2.0)" : "OFF"}</span>
          </div>

          <div className={`indicator-box ${lockClamp ? "active" : ""}`}>
            <span className="icon">🔒</span>
            <span className="label">Lock Clamp</span>
            <span className="value font-mono">{lockClamp ? "LOCKED (DB2.1)" : "OPEN"}</span>
          </div>

          <div className={`indicator-box ${zLiftUp ? "active" : ""}`}>
            <span className="icon">⬆️</span>
            <span className="label">Z-Lift</span>
            <span className="value font-mono">{zLiftUp ? "UP (DB2.2)" : "DOWN"}</span>
          </div>

          <div className={`indicator-box ${eStopOk ? "active-ok" : "active-error"}`}>
            <span className="icon">🛑</span>
            <span className="label">E-Stop Status</span>
            <span className="value font-mono">{eStopOk ? "OK (DB2.6)" : "ACTIVE"}</span>
          </div>
        </div>

        {/* Manual Direct Hardware Controls Toolbar - ONLY VISIBLE IN MANUAL MODE */}
        {systemMode === "MANUAL" && (
          <div className="plc-manual-controls-section">
            <div className="manual-section-title flex-between">
              <span className="font-mono text-cyan">🎮 ĐIỀU KHIỂN THỦ CÔNG PLC (MANUAL OVERRIDE):</span>
              <span className="mode-indicator-tag active-manual">MANUAL SẴN SÀNG</span>
            </div>

            {feedback && <div className="manual-feedback-pill font-mono">{feedback}</div>}

            <div className="manual-btn-grid-4">
              <button
                type="button"
                className="btn-manual-plc"
                onClick={() => handleCommand(() => controlPlcLock(true), "Đã kích hoạt khóa Drone (LOCK)")}
                disabled={loading}
                title="Khóa kẹp cơ khí cố định Drone"
              >
                🔒 Khóa Drone
              </button>
              <button
                type="button"
                className="btn-manual-plc"
                onClick={() => handleCommand(() => controlPlcLock(false), "Đã mở khóa Drone (UNLOCK)")}
                disabled={loading}
                title="Mở khóa giải phóng Drone"
              >
                🔓 Mở Khóa Drone
              </button>
              <button
                type="button"
                className="btn-manual-plc"
                onClick={() => handleCommand(() => controlPlcHatch(true), "Đã kích hoạt Nâng Trục Z (Z_UP)")}
                disabled={loading}
                title="Nâng bệ đỡ Z lên vị trí cao"
              >
                ⬆️ Nâng Trục Z
              </button>
              <button
                type="button"
                className="btn-manual-plc"
                onClick={() => handleCommand(() => controlPlcHatch(false), "Đã kích hoạt Hạ Trục Z (Z_DOWN)")}
                disabled={loading}
                title="Hạ bệ đỡ Z xuống vị trí gốc"
              >
                ⬇️ Hạ Trục Z
              </button>
            </div>

            <div className="manual-btn-grid-3">
              <button
                type="button"
                className="btn-manual-plc btn-plc-green"
                onClick={() => handleCommand(startPlc, "Đã khởi động PLC (START_PLC)")}
                disabled={loading}
                title="Bật / Kích hoạt hệ thống PLC"
              >
                ▶️ Start PLC
              </button>
              <button
                type="button"
                className="btn-manual-plc btn-plc-red"
                onClick={() => handleCommand(stopPlc, "Đã dừng PLC (STOP_PLC)")}
                disabled={loading}
                title="Dừng hệ thống PLC"
              >
                ⏹ Stop PLC
              </button>
              <button
                type="button"
                className="btn-manual-plc btn-plc-yellow"
                onClick={() => handleCommand(resetPlc, "Đã reset lỗi PLC (RESET_PLC)")}
                disabled={loading}
                title="Reset cờ báo lỗi PLC"
              >
                🔄 Reset Lỗi
              </button>
            </div>

            <div className="manual-sensor-row flex-between">
              <span className="lbl-mini">Cảm biến Drone Đáp:</span>
              <div className="sensor-toggle-group">
                <button
                  type="button"
                  className={`btn-sensor-toggle ${droneDetected ? "active-detected" : ""}`}
                  onClick={() => handleCommand(() => setSimulatedDroneSensor(true), "Cảm biến: CÓ DRONE ĐÁP")}
                  disabled={loading}
                >
                  ● Có Drone
                </button>
                <button
                  type="button"
                  className={`btn-sensor-toggle ${!droneDetected ? "active-empty" : ""}`}
                  onClick={() => handleCommand(() => setSimulatedDroneSensor(false), "Cảm biến: BÃI ĐÁP TRỐNG")}
                  disabled={loading}
                >
                  ○ Bãi Trống
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
