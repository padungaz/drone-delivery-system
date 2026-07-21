import React, { useState } from "react";
import { setFlightMode, moveRelative, startCamera, stopCamera, armDrone, disarmDrone } from "../services/api";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  droneStatus?: any;
};

const FLIGHT_MODES = [
  { label: "Offboard", value: "OFFBOARD" },
  { label: "Position (POSCTL)", value: "POSCTL" },
  { label: "Altitude (ALTCTL)", value: "ALTCTL" },
  { label: "Stabilized", value: "STABILIZED" },
  { label: "Hold / Loiter", value: "AUTO.LOITER" },
  { label: "Takeoff", value: "AUTO.TAKEOFF" },
  { label: "Land", value: "AUTO.LAND" },
  { label: "Precision Land", value: "AUTO.PRECLAND" },
  { label: "Return (RTL)", value: "AUTO.RTL" },
  { label: "Mission", value: "AUTO.MISSION" },
];

export function ManualControlModal({ isOpen, onClose, droneStatus }: Props) {
  const [armLoading, setArmLoading] = useState<"arm" | "disarm" | "force" | null>(null);
  const [armMsg, setArmMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const isArmed: boolean = droneStatus?.armed ?? false;

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

  const handleArm = async () => {
    setArmLoading("arm");
    setArmMsg(null);
    try {
      const res = await armDrone();
      const data = await res.json();
      setArmMsg(res.ok ? `✅ ${data.status}` : `❌ ${data.detail ?? "Failed"}`);
    } catch {
      setArmMsg("❌ Network error");
    } finally {
      setArmLoading(null);
    }
  };

  const handleDisarm = async (force = false) => {
    if (force && !window.confirm("⚠️ Force DISARM will cut motors immediately even if airborne. Confirm?")) return;
    setArmLoading(force ? "force" : "disarm");
    setArmMsg(null);
    try {
      const res = await disarmDrone(force);
      const data = await res.json();
      setArmMsg(res.ok ? `✅ ${data.status}` : `❌ ${data.detail ?? "Failed"}`);
    } catch {
      setArmMsg("❌ Network error");
    } finally {
      setArmLoading(null);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <button onClick={onClose} className="modal-close" title="Close Modal">✕</button>
        <h2>Manual Control</h2>

        {/* ── ARM / DISARM ─────────────────────────────────────── */}
        <div className="modal-section">
          <h3>
            Arm / Disarm&nbsp;
            <span className={`armed-badge ${isArmed ? "armed" : "disarmed"}`}>
              {isArmed ? "🔴 ARMED" : "🟢 DISARMED"}
            </span>
          </h3>
          <div className="arm-controls">
            <button
              id="btn-manual-arm"
              className="btn btn-arm"
              disabled={isArmed || armLoading !== null}
              onClick={handleArm}
              title={isArmed ? "Already armed" : "ARM motors (drone must be IDLE)"}
            >
              {armLoading === "arm" ? "Arming…" : "⚡ ARM"}
            </button>
            <button
              id="btn-manual-disarm"
              className="btn btn-disarm"
              disabled={!isArmed || armLoading !== null}
              onClick={() => handleDisarm(false)}
              title={!isArmed ? "Already disarmed" : "DISARM motors (drone must be landed)"}
            >
              {armLoading === "disarm" ? "Disarming…" : "🛑 DISARM"}
            </button>
            <button
              id="btn-force-disarm"
              className="btn btn-force-disarm"
              disabled={armLoading !== null}
              onClick={() => handleDisarm(true)}
              title="⚠️ Force cut motors immediately — USE ONLY IN EMERGENCY"
            >
              {armLoading === "force" ? "Forcing…" : "☠️ FORCE DISARM"}
            </button>
          </div>
          {armMsg && <p className="action-message">{armMsg}</p>}
        </div>

        {/* ── Flight Modes ─────────────────────────────────────── */}
        <div className="modal-section">
          <h3>Flight Modes</h3>
          <div className="modal-grid-3">
            {FLIGHT_MODES.map((mode) => (
              <button
                key={mode.value}
                onClick={() => handleSetMode(mode.value)}
                className={`btn-mode ${droneStatus?.flight_mode === mode.value ? "active" : ""}`}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── Movement ─────────────────────────────────────────── */}
        <div className="modal-section">
          <h3>Movement (10cm steps)</h3>
          <p className="warning-text">Requires OFFBOARD mode + ARMED.</p>
          <div className="movement-box">
            {/* Z axis */}
            <div className="z-axis-controls">
              <button onClick={() => handleMove(0, 0, -0.1)} className="btn-move round" title="Up">UP</button>
              <span className="z-label">Z-Axis</span>
              <button onClick={() => handleMove(0, 0, 0.1)} className="btn-move round" title="Down">DN</button>
            </div>

            {/* X/Y axis (D-pad) */}
            <div className="modal-grid-dpad">
              <div />
              <button onClick={() => handleMove(0.1, 0, 0)} className="btn-move" title="Forward">▲</button>
              <div />
              <button onClick={() => handleMove(0, -0.1, 0)} className="btn-move" title="Left">◀</button>
              <button onClick={() => handleMove(-0.1, 0, 0)} className="btn-move" title="Backward">▼</button>
              <button onClick={() => handleMove(0, 0.1, 0)} className="btn-move" title="Right">▶</button>
            </div>
          </div>
        </div>

        {/* ── Camera ───────────────────────────────────────────── */}
        <div className="modal-section">
          <h3>Camera</h3>
          <div className="camera-controls">
            <button onClick={() => handleCamera("start")} className="btn btn-cam-start">Start Camera</button>
            <button onClick={() => handleCamera("stop")} className="btn btn-cam-stop">Stop Camera</button>
          </div>
        </div>

      </div>
    </div>
  );
}
