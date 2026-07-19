import React from "react";
import { setFlightMode, moveRelative, startCamera, stopCamera } from "../services/api";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  droneStatus?: any;
};

const FLIGHT_MODES = [
  { label: "Offboard", value: "OFFBOARD" },
  { label: "Position", value: "POSCTL" },
  { label: "Hold", value: "HOLD" },
  { label: "Takeoff", value: "AUTO.TAKEOFF" },
  { label: "Land", value: "AUTO.LAND" },
  { label: "Return (RTL)", value: "AUTO.RTL" },
  { label: "Mission", value: "AUTO.MISSION" },
];

export function ManualControlModal({ isOpen, onClose, droneStatus }: Props) {
  if (!isOpen) return null;

  const handleSetMode = async (mode: string) => {
    try {
      await setFlightMode(mode);
    } catch (err) {
      console.error("Failed to set mode", err);
    }
  };

  const handleMove = async (dx: number, dy: number, dz: number) => {
    try {
      await moveRelative(dx, dy, dz);
    } catch (err) {
      console.error("Failed to move", err);
    }
  };

  const handleCamera = async (action: "start" | "stop") => {
    try {
      if (action === "start") await startCamera();
      else await stopCamera();
    } catch (err) {
      console.error(`Failed to ${action} camera`, err);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <button
          onClick={onClose}
          className="modal-close"
          title="Close Modal"
        >
          ✕
        </button>
        <h2>Manual Control</h2>
        
        {/* Flight Modes */}
        <div className="modal-section">
          <h3>Flight Modes</h3>
          <div className="modal-grid-3">
            {FLIGHT_MODES.map((mode) => (
              <button
                key={mode.value}
                onClick={() => handleSetMode(mode.value)}
                className={`btn-mode ${
                  droneStatus?.flight_mode === mode.value ? "active" : ""
                }`}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>

        {/* Movement */}
        <div className="modal-section">
          <h3>Movement (10cm steps)</h3>
          <p className="warning-text">Requires OFFBOARD mode to be active.</p>
          <div className="movement-box">
            {/* Z axis */}
            <div className="z-axis-controls">
              <button
                onClick={() => handleMove(0, 0, -0.1)} // dz = -0.1 is UP
                className="btn-move round"
                title="Up"
              >
                UP
              </button>
              <span className="z-label">Z-Axis</span>
              <button
                onClick={() => handleMove(0, 0, 0.1)} // dz = 0.1 is DOWN
                className="btn-move round"
                title="Down"
              >
                DN
              </button>
            </div>

            {/* X/Y axis (D-pad) */}
            <div className="modal-grid-dpad">
              <div />
              <button
                onClick={() => handleMove(0.1, 0, 0)} // dx = 0.1 is Forward
                className="btn-move"
                title="Forward"
              >
                ▲
              </button>
              <div />
              <button
                onClick={() => handleMove(0, -0.1, 0)} // dy = -0.1 is Left
                className="btn-move"
                title="Left"
              >
                ◀
              </button>
              <button
                onClick={() => handleMove(-0.1, 0, 0)} // dx = -0.1 is Backward
                className="btn-move"
                title="Backward"
              >
                ▼
              </button>
              <button
                onClick={() => handleMove(0, 0.1, 0)} // dy = 0.1 is Right
                className="btn-move"
                title="Right"
              >
                ▶
              </button>
            </div>
          </div>
        </div>

        {/* Camera Control */}
        <div className="modal-section">
          <h3>Camera</h3>
          <div className="camera-controls">
            <button
              onClick={() => handleCamera("start")}
              className="btn btn-cam-start"
            >
              Start Camera
            </button>
            <button
              onClick={() => handleCamera("stop")}
              className="btn btn-cam-stop"
            >
              Stop Camera
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
