import type { Telemetry } from "../types/drone";

interface Props {
  telemetry: Telemetry | null;
  droneOnline: boolean;
}

export function TelemetryPanel({ telemetry, droneOnline }: Props) {
  if (!telemetry) {
    return (
      <section className="panel telemetry-panel">
        <h2>📊 GCS HUD Telemetry</h2>
        <div className="telemetry-waiting">
          <span className="spinner-dot" />
          <p className="muted">
            {droneOnline ? "Connecting telemetry stream..." : "UAV Offline — Waiting for MAVLink telemetry"}
          </p>
        </div>
      </section>
    );
  }

  // Extract telemetry values safely with default fallbacks
  const roll = telemetry.roll ?? 0;
  const pitch = telemetry.pitch ?? 0;
  const heading = telemetry.heading ?? 0;
  const altAgl = telemetry.altitude_agl ?? 0;
  const altRel = telemetry.altitude_relative ?? 0;
  const speed = telemetry.ground_speed ?? 0;
  const lat = telemetry.latitude ?? 0;
  const lon = telemetry.longitude ?? 0;
  const sats = telemetry.gps_satellite ?? 0;

  // Calculate battery color state
  const batPct = Math.max(0, Math.min(100, telemetry.battery ?? 100));
  const batColor = batPct > 50 ? "#00E676" : batPct > 20 ? "#FFB800" : "#FF2A6D";

  // AGL Altitude percentage for meter gauge (max 10m scale)
  const aglMeterPct = Math.min(100, (altAgl / 10.0) * 100);

  return (
    <section className="panel telemetry-panel">
      <div className="telemetry-header">
        <h2>📊 GCS HUD Telemetry</h2>
        <span className={`armed-pill ${telemetry.armed ? "armed" : "disarmed"}`}>
          {telemetry.armed ? "⚡ ARMED" : "🔒 DISARMED"}
        </span>
      </div>

      {/* Main HUD Gauge Bar */}
      <div className="hud-gauges-grid">
        {/* Gauge 1: Attitude Roll / Pitch / Yaw */}
        <div className="hud-card attitude-card">
          <div className="hud-card-title">ATTITUDE & HEADING</div>
          <div className="attitude-indicators">
            <div className="att-gauge">
              <span className="att-val">{roll.toFixed(1)}°</span>
              <span className="att-lbl">ROLL</span>
            </div>
            <div className="att-gauge">
              <span className="att-val">{pitch.toFixed(1)}°</span>
              <span className="att-lbl">PITCH</span>
            </div>
            <div className="att-gauge highlight">
              <span className="att-val">{heading.toFixed(0)}°</span>
              <span className="att-lbl">HEADING (YAW)</span>
            </div>
          </div>
        </div>

        {/* Gauge 2: Laser AGL Altitude Vertical Bar (MTF-02P) */}
        <div className="hud-card altitude-card">
          <div className="hud-card-title">LASER RANGEFINDER (AGL)</div>
          <div className="agl-meter-wrapper">
            <div className="agl-bar-outer">
              <div className="agl-bar-fill" style={{ height: `${aglMeterPct}%` }} />
            </div>
            <div className="agl-values">
              <span className="agl-main">{altAgl.toFixed(2)} m</span>
              <span className="agl-sub">Rel Alt: {altRel.toFixed(1)}m</span>
            </div>
          </div>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="telemetry-metrics-grid">
        <div className="metric-box">
          <span className="metric-lbl">STATE</span>
          <span className="metric-val state-val">{telemetry.drone_state || "UNKNOWN"}</span>
        </div>
        <div className="metric-box">
          <span className="metric-lbl">FLIGHT MODE</span>
          <span className="metric-val mode-val">{telemetry.flight_mode || "UNKNOWN"}</span>
        </div>
        <div className="metric-box">
          <span className="metric-lbl">BATTERY</span>
          <span className="metric-val" style={{ color: batColor }}>
            {batPct.toFixed(0)}%
          </span>
        </div>
        <div className="metric-box">
          <span className="metric-lbl">SPEED</span>
          <span className="metric-val">{speed.toFixed(1)} m/s</span>
        </div>
        <div className="metric-box">
          <span className="metric-lbl">GPS SATS</span>
          <span className="metric-val gps-val">📡 {sats}</span>
        </div>
        <div className="metric-box">
          <span className="metric-lbl">ARUCO VISION</span>
          <span className={`metric-val ${telemetry.aruco_detected ? "aruco-on" : "aruco-off"}`}>
            {telemetry.aruco_detected ? "🎯 DETECTED" : "SEARCHING"}
          </span>
        </div>
      </div>

      {/* Coordinates Footer */}
      <div className="gps-coords-bar">
        <span>LAT: <strong>{lat.toFixed(7)}°</strong></span>
        <span>LON: <strong>{lon.toFixed(7)}°</strong></span>
        <span>PHASE: <strong>{telemetry.landing_phase?.toUpperCase() || "IDLE"}</strong></span>
      </div>
    </section>
  );
}

