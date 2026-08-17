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
}: Props) {
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
      </div>
    </div>
  );
}
