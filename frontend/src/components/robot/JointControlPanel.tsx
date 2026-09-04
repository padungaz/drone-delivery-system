import { useState } from "react";

interface Props {
  initialJoints?: number[];
  initialGripperState?: "OPEN" | "CLOSED";
  initialGripperForce?: number;
  disabled?: boolean;
}

export function JointControlPanel({
  initialJoints = [-45.2, 32.1, -88.3, 90.0, 15.2, -18.0],
  initialGripperState = "OPEN",
  initialGripperForce = 80,
  disabled = false,
}: Props) {
  const [joints, setJoints] = useState<number[]>(initialJoints);
  const [gripperState, setGripperState] = useState<"OPEN" | "CLOSED">(
    initialGripperState
  );
  const [gripperForce] = useState<number>(initialGripperForce);

  const handleJointChange = (index: number, val: number) => {
    if (disabled) return;
    const next = [...joints];
    next[index] = val;
    setJoints(next);
  };

  return (
    <div className="hmi-card joint-control-panel">
      <div className="card-header flex-between">
        <div className="card-title-group">
          <h3>🦾 JOINTS & GRIPPER</h3>
          <span className="card-subtitle">6-AXIS KINEMATICS & END EFFECTOR</span>
        </div>
        <span className="badge-subtitle">FAIRINO FR3</span>
      </div>

      <div className="card-body joint-layout">
        <div className="joints-sliders-col">
          {joints.map((val, idx) => (
            <div key={`j-${idx + 1}`} className="joint-slider-row">
              <span className="joint-label">J{idx + 1}</span>
              <input
                type="range"
                min={-180}
                max={180}
                step={0.1}
                value={val}
                disabled={disabled}
                onChange={(e) => handleJointChange(idx, parseFloat(e.target.value))}
                className="joint-range-input"
              />
              <span className="joint-angle-value">
                {val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2)}°
              </span>
            </div>
          ))}
        </div>

        <div className="gripper-status-col">
          <div className="gripper-header flex-between">
            <span>GRIPPER</span>
            <span
              className={`gripper-badge ${
                gripperState === "OPEN" ? "open" : "closed"
              }`}
            >
              {gripperState === "OPEN" ? "🟢 ĐANG MỞ" : "🔵 ĐÃ ĐÓNG"}
            </span>
          </div>

          <div className="gripper-graphic-box">
            <svg className="gripper-svg" viewBox="0 0 100 80">
              {/* Gripper Base Body */}
              <rect x="35" y="10" width="30" height="20" rx="4" fill="#1e293b" stroke="#00f0ff" strokeWidth="1.5" />
              <rect x="42" y="5" width="16" height="5" fill="#334155" />
              
              {/* Left Finger Mechanical Jaw */}
              <g className={`gripper-finger-left ${gripperState.toLowerCase()}`}>
                <path d="M 35 30 L 25 50 L 30 65 L 35 65 L 30 52 L 40 30 Z" fill="#00f0ff" stroke="#00f0ff" />
              </g>

              {/* Right Finger Mechanical Jaw */}
              <g className={`gripper-finger-right ${gripperState.toLowerCase()}`}>
                <path d="M 65 30 L 75 50 L 70 65 L 65 65 L 70 52 L 60 30 Z" fill="#00f0ff" stroke="#00f0ff" />
              </g>

              {/* Workpiece Item when Closed */}
              {gripperState === "CLOSED" && (
                <rect x="42" y="50" width="16" height="16" fill="#f59e0b" stroke="#fbbf24" strokeWidth="1" rx="2">
                  <animate attributeName="opacity" values="0.7;1;0.7" dur="1.5s" repeatCount="indefinite" />
                </rect>
              )}
            </svg>
          </div>

          <div className="gripper-force-meter">
            <div className="meter-label flex-between">
              <span>Lực kẹp (Force):</span>
              <strong>{gripperForce}%</strong>
            </div>
            <div className="progress-bar-bg">
              <div
                className="progress-bar-fill force-fill"
                style={{ width: `${gripperForce}%` }}
              ></div>
            </div>
          </div>

          <div className="gripper-toggle-btn">
            <button
              type="button"
              className={`btn-action-sm ${
                gripperState === "OPEN" ? "btn-teal" : "btn-cyan"
              }`}
              disabled={disabled}
              title={disabled ? "Robot đang bận" : undefined}
              onClick={() =>
                setGripperState(gripperState === "OPEN" ? "CLOSED" : "OPEN")
              }
            >
              {gripperState === "OPEN" ? "🔒 ĐÓNG KẸP" : "🔓 MỞ KẸP"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
