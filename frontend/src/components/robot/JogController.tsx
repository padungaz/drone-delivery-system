import { useState } from "react";

interface Props {
  onJogCommand?: (axis: string, step: number) => void;
}

export function JogController({ onJogCommand }: Props) {
  const [jogMode, setJogMode] = useState<"JOGGING" | "TEACH">("JOGGING");
  const [stepSize, setStepSize] = useState<0.1 | 1 | 10>(1);
  const [speed, setSpeed] = useState<number>(50);

  const handleJog = (axis: string) => {
    if (onJogCommand) {
      onJogCommand(axis, stepSize);
    }
  };

  return (
    <div className="hmi-card jog-controller">
      <div className="card-header flex-between">
        <div className="card-title-group">
          <h3>🕹️ JOG CONTROLLER</h3>
          <span className="card-subtitle">MANUAL AXIS MOTION & TEACHING</span>
        </div>
        <div className="jog-mode-tabs">
          <button
            type="button"
            className={`tab-btn-sm ${jogMode === "JOGGING" ? "active" : ""}`}
            onClick={() => setJogMode("JOGGING")}
          >
            JOGGING
          </button>
          <button
            type="button"
            className={`tab-btn-sm ${jogMode === "TEACH" ? "active" : ""}`}
            onClick={() => setJogMode("TEACH")}
          >
            TEACH MODE
          </button>
        </div>
      </div>

      <div className="card-body jog-layout">
        <div className="jog-options-bar">
          <div className="step-size-group">
            <span className="group-label">STEP:</span>
            <div className="btn-group-sm">
              {([0.1, 1, 10] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`step-btn ${stepSize === s ? "active" : ""}`}
                  onClick={() => setStepSize(s)}
                >
                  {s}mm
                </button>
              ))}
            </div>
          </div>

          <div className="speed-slider-group">
            <div className="flex-between speed-header">
              <span>SPEED:</span>
              <strong className="speed-value">{speed}%</strong>
            </div>
            <input
              type="range"
              min={5}
              max={100}
              value={speed}
              onChange={(e) => setSpeed(parseInt(e.target.value, 10))}
              className="speed-range-input"
            />
          </div>
        </div>

        <div className="jog-dpad-container">
          <div className="dpad-grid">
            <button
              type="button"
              className="dpad-btn dpad-z-plus"
              onClick={() => handleJog("Z+")}
              title="Jog Z-axis Up"
            >
              <span className="dpad-axis">Z+</span>
              <span className="dpad-arrow">▲</span>
            </button>

            <button
              type="button"
              className="dpad-btn dpad-y-plus"
              onClick={() => handleJog("Y+")}
              title="Jog Y-axis Forward"
            >
              <span className="dpad-axis">Y+</span>
              <span className="dpad-arrow">▲</span>
            </button>

            <button
              type="button"
              className="dpad-btn dpad-z-minus"
              onClick={() => handleJog("Z-")}
              title="Jog Z-axis Down"
            >
              <span className="dpad-axis">Z-</span>
              <span className="dpad-arrow">▼</span>
            </button>

            <button
              type="button"
              className="dpad-btn dpad-x-minus"
              onClick={() => handleJog("X-")}
              title="Jog X-axis Left"
            >
              <span className="dpad-arrow">◀</span>
              <span className="dpad-axis">X-</span>
            </button>

            <button
              type="button"
              className="dpad-btn dpad-home"
              onClick={() => handleJog("HOME")}
              title="Return to Home Position"
            >
              <span className="dpad-icon">🏠</span>
              <span className="dpad-axis">HOME</span>
            </button>

            <button
              type="button"
              className="dpad-btn dpad-x-plus"
              onClick={() => handleJog("X+")}
              title="Jog X-axis Right"
            >
              <span className="dpad-axis">X+</span>
              <span className="dpad-arrow">▶</span>
            </button>

            <div className="dpad-placeholder"></div>

            <button
              type="button"
              className="dpad-btn dpad-y-minus"
              onClick={() => handleJog("Y-")}
              title="Jog Y-axis Backward"
            >
              <span className="dpad-axis">Y-</span>
              <span className="dpad-arrow">▼</span>
            </button>

            <div className="dpad-placeholder"></div>
          </div>
        </div>
      </div>
    </div>
  );
}

