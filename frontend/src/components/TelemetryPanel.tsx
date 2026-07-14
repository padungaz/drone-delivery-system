import type { Telemetry } from "../types/drone";

interface Props {
  telemetry: Telemetry | null;
  droneOnline: boolean;
}

function StatusRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="status-row">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
    </div>
  );
}

export function TelemetryPanel({ telemetry, droneOnline }: Props) {
  if (!telemetry) {
    return (
      <section className="panel telemetry-panel">
        <h2>Telemetry</h2>
        <p className="muted">
          {droneOnline ? "Waiting for telemetry..." : "Drone offline"}
        </p>
      </section>
    );
  }

  return (
    <section className="panel telemetry-panel">
      <h2>Telemetry</h2>
      <div className="status-grid">
        <StatusRow label="State" value={telemetry.drone_state} />
        <StatusRow label="Flight Mode" value={telemetry.flight_mode} />
        <StatusRow label="Latitude" value={telemetry.latitude.toFixed(7)} />
        <StatusRow label="Longitude" value={telemetry.longitude.toFixed(7)} />
        <StatusRow label="Alt (Rel)" value={`${telemetry.altitude_relative.toFixed(1)} m`} />
        <StatusRow label="Alt (AGL)" value={`${telemetry.altitude_agl.toFixed(1)} m`} />
        <StatusRow label="Battery" value={`${telemetry.battery.toFixed(0)}%`} />
        <StatusRow label="Speed" value={`${telemetry.ground_speed.toFixed(1)} m/s`} />
        <StatusRow label="Heading" value={`${telemetry.heading.toFixed(0)}°`} />
        <StatusRow label="GPS Sats" value={telemetry.gps_satellite} />
        <StatusRow label="ArUco" value={telemetry.aruco_detected ? "DETECTED" : "NONE"} />
        <StatusRow label="Landing" value={telemetry.landing_status} />
        <StatusRow label="Armed" value={telemetry.armed ? "YES" : "NO"} />
      </div>
    </section>
  );
}
