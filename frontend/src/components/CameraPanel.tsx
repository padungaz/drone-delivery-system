import { useState } from "react";
import type { ArucoDetection, CameraStatus } from "../types/drone";
import { startCamera, stopCamera } from "../services/api";

interface Props {
  cameraStatus: CameraStatus;
  arucoDetection: ArucoDetection | null;
  droneOnline: boolean;
}

const STATUS_CONFIG: Record<CameraStatus, { label: string; cls: string; icon: string }> = {
  OFF:   { label: "Camera OFF",   cls: "cam-off",   icon: "🔴" },
  ON:    { label: "Camera ON",    cls: "cam-on",    icon: "🟢" },
  ERROR: { label: "Camera ERROR", cls: "cam-error", icon: "🟡" },
};

export function CameraPanel({ cameraStatus, arucoDetection, droneOnline }: Props) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const isOn = cameraStatus === "ON";
  const statusInfo = STATUS_CONFIG[cameraStatus];

  const handleToggle = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const res = isOn ? await stopCamera() : await startCamera();
      const data = await res.json();
      if (!res.ok) {
        setMessage(`Error: ${data.detail ?? "Request failed"}`);
      } else {
        setMessage(data.status ?? "OK");
      }
    } catch (err) {
      setMessage(`Error: ${err instanceof Error ? err.message : "Network error"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel camera-panel">
      <h2>Camera & ArUco</h2>

      {/* Status badge */}
      <div className="camera-status-row">
        <span className={`cam-badge ${statusInfo.cls}`}>
          {statusInfo.icon} {statusInfo.label}
        </span>
        <button
          id="btn-test-camera"
          className={`btn ${isOn ? "btn-stop" : "btn-camera"}`}
          disabled={!droneOnline || loading}
          onClick={handleToggle}
          title={
            !droneOnline
              ? "Drone must be online to test camera"
              : isOn
              ? "Stop camera and ArUco detection"
              : "Open USB camera and start ArUco detection"
          }
        >
          {loading ? "Sending…" : isOn ? "⏹ Stop Camera" : "📷 Test Camera"}
        </button>
      </div>

      {/* ArUco detection info */}
      {isOn && (
        <div className="aruco-info">
          {arucoDetection?.aruco_detected ? (
            <div className="aruco-grid">
              <div className="aruco-row">
                <span className="label">ArUco</span>
                <span className="value aruco-yes">✅ DETECTED</span>
              </div>
              <div className="aruco-row">
                <span className="label">Marker ID</span>
                <span className="value">{arucoDetection.marker_id}</span>
              </div>
              <div className="aruco-row">
                <span className="label">Center</span>
                <span className="value">
                  ({arucoDetection.center_x}, {arucoDetection.center_y})
                </span>
              </div>
              <div className="aruco-row">
                <span className="label">Offset</span>
                <span className="value">
                  dx: {arucoDetection.offset_x}, dy: {arucoDetection.offset_y}
                </span>
              </div>
              <div className="aruco-row">
                <span className="label">Frame</span>
                <span className="value">
                  {arucoDetection.image_width}×{arucoDetection.image_height}
                </span>
              </div>
            </div>
          ) : (
            <div className="aruco-none">
              <span>🔍 No ArUco marker detected</span>
              {arucoDetection === null && (
                <span className="muted"> — Waiting for first scan...</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Response message */}
      {message && <p className="action-message">{message}</p>}
    </section>
  );
}
