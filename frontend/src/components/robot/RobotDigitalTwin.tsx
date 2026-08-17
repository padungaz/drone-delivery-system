import { useState } from "react";

interface Props {
  tcpPosition?: {
    x: number;
    y: number;
    z: number;
    rx: number;
    ry: number;
    rz: number;
  };
}

export function RobotDigitalTwin({
  tcpPosition = {
    x: 320.25,
    y: 152.10,
    z: 460.30,
    rx: 188.0,
    ry: 0.0,
    rz: 90.0,
  },
}: Props) {
  const [viewMode, setViewMode] = useState<"3d" | "top" | "side" | "front">("3d");

  return (
    <div className="hmi-card robot-digital-twin">
      <div className="card-header flex-between">
        <div className="card-title-group">
          <h3>🦾 ROBOT DIGITAL TWIN</h3>
          <span className="card-subtitle">FAIRINO FR3 6-DOF REALTIME MODEL</span>
        </div>
        <div className="view-mode-buttons">
          <button
            type="button"
            className={`btn-view ${viewMode === "3d" ? "active" : ""}`}
            onClick={() => setViewMode("3d")}
          >
            🌐 3D
          </button>
          <button
            type="button"
            className={`btn-view ${viewMode === "top" ? "active" : ""}`}
            onClick={() => setViewMode("top")}
          >
            ⬆️ Top
          </button>
          <button
            type="button"
            className={`btn-view ${viewMode === "side" ? "active" : ""}`}
            onClick={() => setViewMode("side")}
          >
            ➡️ Side
          </button>
          <button
            type="button"
            className={`btn-view ${viewMode === "front" ? "active" : ""}`}
            onClick={() => setViewMode("front")}
          >
            🖼️ Front
          </button>
          <button
            type="button"
            className="btn-view btn-reset"
            onClick={() => setViewMode("3d")}
          >
            🔄 Reset
          </button>
        </div>
      </div>

      <div className="card-body twin-canvas-container">
        <div className="twin-viewport">
          {/* Cyber 3D Grid & Animated Robotic Arm Graphic */}
          <div className="cyber-grid-floor"></div>

          <svg className="robot-svg-visualizer" viewBox="0 0 300 160">
            <defs>
              <linearGradient id="armGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#00f0ff" />
                <stop offset="100%" stopColor="#3b82f6" />
              </linearGradient>
              <linearGradient id="baseGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#1e293b" />
                <stop offset="100%" stopColor="#0f172a" />
              </linearGradient>
              <filter id="cyanGlow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Base Pedestal */}
            <ellipse cx="150" cy="140" rx="45" ry="12" fill="url(#baseGrad)" stroke="#00f0ff" strokeWidth="1.5" />
            <rect x="135" y="115" width="30" height="25" fill="#1e293b" stroke="#334155" />
            
            {/* Joint J1 Base Rotary */}
            <circle cx="150" cy="115" r="10" fill="#00f0ff" filter="url(#cyanGlow)" />

            {/* Link 1 (Lower Arm) */}
            <line x1="150" y1="115" x2="110" y2="65" stroke="url(#armGrad)" strokeWidth="8" strokeLinecap="round" />
            
            {/* Joint J2 Shoulder */}
            <circle cx="110" cy="65" r="8" fill="#3b82f6" stroke="#00f0ff" strokeWidth="1.5" />

            {/* Link 2 (Upper Arm) */}
            <line x1="110" y1="65" x2="180" y2="40" stroke="url(#armGrad)" strokeWidth="6" strokeLinecap="round" />

            {/* Joint J3 Elbow */}
            <circle cx="180" cy="40" r="7" fill="#00f0ff" filter="url(#cyanGlow)" />

            {/* Link 3 (Forearm) */}
            <line x1="180" y1="40" x2="220" y2="70" stroke="#00f0ff" strokeWidth="4" strokeLinecap="round" />

            {/* Wrist & End Effector Tool (TCP Target) */}
            <circle cx="220" cy="70" r="5" fill="#a855f7" />
            <path d="M216 70 L224 70 M220 66 L220 74" stroke="#10b981" strokeWidth="1.5" />

            {/* Target Laser Beacon Dot */}
            <circle cx="220" cy="70" r="9" fill="none" stroke="#10b981" strokeWidth="1" strokeDasharray="2,2">
              <animate attributeName="r" values="6;12;6" dur="2s" repeatCount="indefinite" />
            </circle>
          </svg>

          <div className="view-mode-overlay">{viewMode.toUpperCase()} VIEW MODE</div>
        </div>

        <div className="tcp-readout-bar">
          <div className="tcp-title flex-between">
            <span>📍 TCP POSITION & ORIENTATION</span>
            <span className="unit-tag">FRAME: BASE</span>
          </div>
          <div className="tcp-values-grid">
            <div className="tcp-cell">
              <span className="label">X</span>
              <span className="value val-x">{tcpPosition.x.toFixed(2)} <small>mm</small></span>
            </div>
            <div className="tcp-cell">
              <span className="label">Y</span>
              <span className="value val-y">{tcpPosition.y.toFixed(2)} <small>mm</small></span>
            </div>
            <div className="tcp-cell">
              <span className="label">Z</span>
              <span className="value val-z">{tcpPosition.z.toFixed(2)} <small>mm</small></span>
            </div>
            <div className="tcp-cell">
              <span className="label">Roll</span>
              <span className="value val-r">{tcpPosition.rx.toFixed(2)}°</span>
            </div>
            <div className="tcp-cell">
              <span className="label">Pitch</span>
              <span className="value val-p">{tcpPosition.ry.toFixed(2)}°</span>
            </div>
            <div className="tcp-cell">
              <span className="label">Yaw</span>
              <span className="value val-yw">{tcpPosition.rz.toFixed(2)}°</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
