import React, { useState, useEffect } from "react";

export interface MotionStepInfo {
  stepIndex: number; // 1 to 4
  stepName: string;
  stepDesc: string;
}

export interface SocketLogEntry {
  id: string;
  time: string;
  type: "TX" | "RX" | "ERR";
  payload: string;
  duration?: string;
}

interface Props {
  state?: string;
  mode?: string;
  speed?: number;
  cycleTime?: string;
  program?: string;
  errorCode?: string;
  servo?: boolean;
  brake?: boolean;
  power?: boolean;
  gripperHolding?: boolean;
  currentSlot?: string | null;
  activeCommand?: string | null;
  elapsedSeconds?: number;
  lastCycleDuration?: number | null;
  socketLogs?: SocketLogEntry[];
  latencyMs?: number;
  simulatorMode?: boolean;
  onToggleSimulator?: (sim: boolean) => void;
}

export const RobotStatusCard = React.memo(function RobotStatusCard({
  state = "IDLE",
  mode = "AUTO",
  speed = 100,
  cycleTime = "00:00:00",
  _program: _p = "HOME",
  _errorCode: _e = "-",
  servo = true,
  brake = true,
  power = true,
  gripperHolding = false,
  currentSlot = "HOME",
  activeCommand = null,
  elapsedSeconds: parentElapsed = 0,
  lastCycleDuration = null,
  socketLogs = [],
  latencyMs = 1.5,
  simulatorMode = false,
  onToggleSimulator,
}: Props & { _program?: string; _errorCode?: string }) {
  const [showSocketTraffic, setShowSocketTraffic] = useState(false);
  const [internalElapsed, setInternalElapsed] = useState(0);

  // Local stopwatch timer only running when activeCommand is active
  useEffect(() => {
    let timer: any = null;
    if (activeCommand) {
      const startTime = Date.now();
      setInternalElapsed(0);
      timer = setInterval(() => {
        setInternalElapsed((Date.now() - startTime) / 1000);
      }, 150);
    } else {
      setInternalElapsed(0);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [activeCommand]);

  const elapsedSeconds = activeCommand ? internalElapsed : parentElapsed;

  const isMoving = state === "MOVING" || state === "PICKING" || state === "PLACING" || Boolean(activeCommand);
  const isError = state === "ERROR" || state === "ESTOP";
  const isOnline = state !== "OFFLINE" || simulatorMode;

  // Calculate Motion Progress (approx 13s for PICK/STORE, 3.5s for MOVE_HOME)
  const isHomeCmd = activeCommand?.includes("HOME");
  const estimatedTotalSec = isHomeCmd ? 3.5 : 13.0;
  const progressPercent = isMoving
    ? Math.min(Math.round((elapsedSeconds / estimatedTotalSec) * 100), 98)
    : state === "READY" || state === "IDLE"
    ? 100
    : 0;

  // Determine current active step in 4-stage motion
  const currentStep = isMoving
    ? elapsedSeconds < 3.0
      ? 1
      : elapsedSeconds < 6.0
      ? 2
      : elapsedSeconds < 9.0
      ? 3
      : 4
    : 0;

  return (
    <div className={`hmi-card robot-status-card ${isMoving ? "card-pulse-moving" : ""}`}>
      {/* Top Header */}
      <div className="card-header flex-between">
        <div className="card-title-group">
          <div className="title-with-badge">
            <h3>🤖 FAIRINO FR3 ROBOT</h3>
            <span className={`status-pill ${isMoving ? "pill-moving" : isError ? "pill-error" : isOnline ? "pill-online" : "pill-offline"}`}>
              {isMoving ? "⚡ ĐANG CHẠY" : isError ? "⚠️ BÁO LỖI" : isOnline ? (simulatorMode ? "🟢 SẴN SÀNG (SIM)" : "🟢 SẴN SÀNG") : "🔴 OFFLINE"}
            </span>
          </div>
          <span className="card-subtitle font-mono">COBOT 6-DOF • TCP: 192.168.57.2:8090 ({latencyMs}ms)</span>
        </div>

        <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
          {onToggleSimulator && (
            <button
              type="button"
              className={`btn-toggle-traffic ${simulatorMode ? "active-sim" : ""}`}
              onClick={() => onToggleSimulator(!simulatorMode)}
              title={simulatorMode ? "Đang bật chế độ mô phỏng (Click để tắt)" : "Bật chế độ mô phỏng Robot ảo"}
            >
              {simulatorMode ? "🎮 SIM: BẬT" : "🎮 BẬT SIM"}
            </button>
          )}
          <button
            type="button"
            className="btn-toggle-traffic"
            onClick={() => setShowSocketTraffic(!showSocketTraffic)}
            title="Bật/Tắt nhật ký truyền nhận Socket LUA"
          >
            {showSocketTraffic ? "Ẩn Socket ▲" : "🔌 Socket Logs ▼"}
          </button>
        </div>
      </div>

      <div className="card-body robot-status-grid-cyber">
        {/* Left Column: Gauge & Speed Indicator */}
        <div className="gauge-cyber-container">
          <div className={`circular-gauge-cyber ${isMoving ? "spin-slow" : ""}`}>
            <svg viewBox="0 0 100 100">
              <circle className="gauge-bg" cx="50" cy="50" r="40" />
              <circle
                className={`gauge-fill ${isMoving ? "fill-moving" : isError ? "fill-error" : "fill-idle"}`}
                cx="50"
                cy="50"
                r="40"
                strokeDasharray={251.2}
                strokeDashoffset={251.2 - (251.2 * (isMoving ? progressPercent : 100)) / 100}
              />
            </svg>
            <div className="gauge-center-cyber">
              <span className="gauge-state-val font-mono">{isMoving ? `${progressPercent}%` : state}</span>
              <span className="gauge-sub-desc font-mono">
                {isMoving ? `${elapsedSeconds.toFixed(1)}s` : currentSlot || "HOME"}
              </span>
            </div>
          </div>
          <div className="speed-badge-box">
            <span className="lbl-mini">TỐC ĐỘ</span>
            <strong className="font-mono text-cyan">{speed}%</strong>
          </div>
        </div>

        {/* Right Column: Parameters List */}
        <div className="status-params-cyber">
          <div className="param-cyber-row">
            <span className="p-lbl">Chế độ vận hành</span>
            <span className={`p-val font-mono ${mode === "AUTO" ? "text-cyan" : "text-amber"}`}>
              {mode === "AUTO" ? "🤖 TỰ ĐỘNG (AUTO)" : "🎮 THỦ CÔNG (MANUAL)"}
            </span>
          </div>

          <div className="param-cyber-row">
            <span className="p-lbl">Vị trí tay máy (TCP)</span>
            <span className="p-val font-mono text-green">
              📍 {currentSlot ? `Ô ${currentSlot}` : "VỊ TRÍ HOME"}
            </span>
          </div>

          <div className="param-cyber-row">
            <span className="p-lbl">Xung hoàn tất O1 (DO1)</span>
            <span className={`p-val font-mono ${gripperHolding ? "text-orange-glow" : "text-slate"}`}>
              {gripperHolding ? "⚡ [DO1: PULSE] BÁO XONG O1" : "⚪ [DO1: OFF] MỨC NGHỈ"}
            </span>
          </div>

          <div className="param-cyber-row">
            <span className="p-lbl">Chu kỳ gần nhất</span>
            <span className="p-val font-mono text-cyan">
              ⏱️ {lastCycleDuration ? `${lastCycleDuration.toFixed(2)}s` : cycleTime || "3.09s"}
            </span>
          </div>

          <div className="param-cyber-row">
            <span className="p-lbl">Lệnh đang chạy</span>
            <span className={`p-val font-mono ${activeCommand ? "text-yellow-glow" : "text-slate"}`}>
              {activeCommand ? `🚀 ${activeCommand}` : "IDLE (CHỜ LỆNH)"}
            </span>
          </div>
        </div>
      </div>

      {/* 4-Stage Motion Stepper Bar (Active during motion or showing last result) */}
      <div className="motion-stepper-container">
        <div className="stepper-header flex-between">
          <span className="stepper-title">
            {isMoving ? `⏳ ĐANG THỰC HIỆN: ${activeCommand}` : `✅ TIẾN TRÌNH QUỸ ĐẠO CƠ KHÍ`}
          </span>
          <span className="stepper-timer font-mono">
            {isMoving ? `⏱️ 00:${String(Math.floor(elapsedSeconds)).padStart(2, "0")}s / ~${estimatedTotalSec}s` : `Hoàn tất: ${lastCycleDuration ? `${lastCycleDuration.toFixed(2)}s` : "Sẵn sàng"}`}
          </span>
        </div>

        <div className="stepper-progress-bar">
          <div className="stepper-fill" style={{ width: `${isMoving ? progressPercent : 100}%` }}></div>
        </div>

        <div className="stepper-steps-grid">
          <div className={`step-item ${currentStep === 1 ? "step-active" : currentStep > 1 || !isMoving ? "step-done" : ""}`}>
            <span className="step-num">1</span>
            <div className="step-text">
              <strong className="step-name">Tiếp cận</strong>
              <span className="step-desc">-100mm Z</span>
            </div>
          </div>

          <div className={`step-item ${currentStep === 2 ? "step-active" : currentStep > 2 || !isMoving ? "step-done" : ""}`}>
            <span className="step-num">2</span>
            <div className="step-text">
              <strong className="step-name">Vào tâm ô</strong>
              <span className="step-desc">Target Pos</span>
            </div>
          </div>

          <div className={`step-item ${currentStep === 3 ? "step-active" : currentStep > 3 || !isMoving ? "step-done" : ""}`}>
            <span className="step-num">3</span>
            <div className="step-text">
              <strong className="step-name">Gắp / Thả</strong>
              <span className="step-desc">Tác vụ ô</span>
            </div>
          </div>

          <div className={`step-item ${currentStep === 4 ? "step-active" : !isMoving ? "step-done" : ""}`}>
            <span className="step-num">4</span>
            <div className="step-text">
              <strong className="step-name">Rút an toàn</strong>
              <span className="step-desc">Safe Home</span>
            </div>
          </div>
        </div>
      </div>

      {/* Hardware Telemetry Flags Bar */}
      <div className="card-footer flags-bar-cyber">
        <div className="led-indicators-group">
          <span className={`flag-badge ${servo && isOnline ? "flag-on" : "flag-off"}`}>
            <span className="dot"></span> SERVO {servo && isOnline ? "ON" : "OFF"}
          </span>
          <span className={`flag-badge ${brake && isOnline ? "flag-on" : "flag-off"}`}>
            <span className="dot"></span> BRAKE {brake && isOnline ? "ON" : "OFF"}
          </span>
          <span className={`flag-badge ${power && isOnline ? "flag-on" : "flag-off"}`}>
            <span className="dot"></span> POWER {power && isOnline ? "ON" : "OFF"}
          </span>
          <span className={`flag-badge ${gripperHolding ? "flag-warning" : "flag-on"}`}>
            <span className="dot"></span> DO1 {gripperHolding ? "ACTIVE" : "READY"}
          </span>
        </div>

        <div className="socket-status-tag font-mono">
          <span>PORT 8090</span>
          <span className="text-cyan">TCP LUA</span>
        </div>
      </div>

      {/* Collapsible Mini Socket Traffic Stream */}
      {showSocketTraffic && (
        <div className="socket-traffic-stream">
          <div className="traffic-header flex-between">
            <span className="font-mono text-cyan">🔌 SOCKET RX/TX REALTIME MONITOR</span>
            <span className="lbl-mini">{socketLogs.length} gói tin</span>
          </div>
          <div className="traffic-list font-mono">
            {socketLogs.length === 0 ? (
              <div className="traffic-empty">Chưa có gói tin Socket nào được gửi/nhận.</div>
            ) : (
              socketLogs.slice(-6).map((log) => (
                <div key={log.id} className={`traffic-row traffic-${log.type.toLowerCase()}`}>
                  <span className="traffic-time">{log.time}</span>
                  <span className="traffic-type">[{log.type}]</span>
                  <span className="traffic-payload">{log.payload}</span>
                  {log.duration && <span className="traffic-duration">{log.duration}</span>}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
});

