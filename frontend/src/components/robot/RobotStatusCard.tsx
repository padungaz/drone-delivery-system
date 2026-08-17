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
}

export function RobotStatusCard({
  state = "IDLE",
  mode = "AUTO",
  speed = 100,
  cycleTime = "00:00:00",
  program = "HOME",
  errorCode = "-",
  servo = true,
  brake = true,
  power = true,
}: Props) {
  const isRunning = state === "RUNNING";
  const isError = state === "ERROR";

  return (
    <div className="hmi-card robot-status-card">
      <div className="card-header">
        <h3>🤖 ROBOT STATUS</h3>
        <span className={`status-badge-dot ${isRunning ? "running" : isError ? "error" : "idle"}`}></span>
      </div>

      <div className="card-body robot-status-grid">
        <div className="gauge-container">
          <div className={`circular-gauge ${isRunning ? "pulse-running" : isError ? "pulse-error" : ""}`}>
            <svg viewBox="0 0 100 100">
              <circle className="gauge-bg" cx="50" cy="50" r="42" />
              <circle className="gauge-fill" cx="50" cy="50" r="42" />
            </svg>
            <div className="gauge-center">
              <span className="gauge-state-text">{state}</span>
              <span className="gauge-sub-text">
                {isRunning ? "ĐANG CHẠY" : isError ? "BÁO LỖI" : "SẴN SÀNG"}
              </span>
            </div>
          </div>
        </div>

        <div className="status-params-list">
          <div className="param-item">
            <span className="param-label">⚙️ Mode</span>
            <span className="param-value highlight-cyan">{mode}</span>
          </div>
          <div className="param-item">
            <span className="param-label">⚡ Speed</span>
            <span className="param-value">{speed}%</span>
          </div>
          <div className="param-item">
            <span className="param-label">⏱️ Cycle Time</span>
            <span className="param-value">{cycleTime}</span>
          </div>
          <div className="param-item">
            <span className="param-label">📜 Program</span>
            <span className="param-value">{program}</span>
          </div>
          <div className="param-item">
            <span className="param-label">⚠️ Error Code</span>
            <span className="param-value">{errorCode}</span>
          </div>
        </div>
      </div>

      <div className="card-footer flags-bar">
        <span className={`flag-badge ${servo ? "active" : ""}`}>
          <span className="dot"></span> Servo {servo ? "ON" : "OFF"}
        </span>
        <span className={`flag-badge ${brake ? "active" : ""}`}>
          <span className="dot"></span> Brake {brake ? "ON" : "OFF"}
        </span>
        <span className={`flag-badge ${power ? "active" : ""}`}>
          <span className="dot"></span> Power {power ? "ON" : "OFF"}
        </span>
      </div>
    </div>
  );
}
