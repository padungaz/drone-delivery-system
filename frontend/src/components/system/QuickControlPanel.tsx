import { useState } from "react";

interface Props {
  onCommand?: (cmd: string, payload?: Record<string, unknown>) => void;
}

export function QuickControlPanel({ onCommand }: Props) {
  const [selectedSlot, setSelectedSlot] = useState<string>("A2");

  const send = (cmd: string, payload?: Record<string, unknown>) => {
    if (onCommand) {
      onCommand(cmd, payload);
    }
  };

  return (
    <div className="hmi-card quick-control-panel">
      <div className="card-header flex-between">
        <h3>⚡ QUICK ACTIONS</h3>
        <span className="badge-subtitle">ROBOT COMMANDS</span>
      </div>

      <div className="card-body quick-actions-grid">
        <button
          type="button"
          className="quick-btn btn-home"
          onClick={() => send("HOME")}
        >
          <span className="btn-icon">🏠</span>
          <div className="btn-text">
            <strong>HOME</strong>
            <small>Move Robot Home</small>
          </div>
        </button>

        <div className="quick-btn-select-group">
          <button
            type="button"
            className="quick-btn btn-pick"
            onClick={() => send("PICK", { slot: selectedSlot })}
          >
            <span className="btn-icon">📦</span>
            <div className="btn-text">
              <strong>PICK SLOT</strong>
              <small>Gắp từ ô kho</small>
            </div>
          </button>
          <select
            className="slot-selector-dropdown"
            value={selectedSlot}
            onChange={(e) => setSelectedSlot(e.target.value)}
          >
            {["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"].map((s) => (
              <option key={s} value={s}>
                Slot {s}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          className="quick-btn btn-store"
          onClick={() => send("STORE", { slot: selectedSlot })}
        >
          <span className="btn-icon">📥</span>
          <div className="btn-text">
            <strong>STORE SLOT</strong>
            <small>Đặt vào ô kho</small>
          </div>
        </button>

        <button
          type="button"
          className="quick-btn btn-pad"
          onClick={() => send("PLACE_PAD")}
        >
          <span className="btn-icon">🚁</span>
          <div className="btn-text">
            <strong>PLACE PAD (N1)</strong>
            <small>Đặt lên Drone</small>
          </div>
        </button>

        <button
          type="button"
          className="quick-btn btn-open-grip"
          onClick={() => send("OPEN_GRIPPER")}
        >
          <span className="btn-icon">🔓</span>
          <div className="btn-text">
            <strong>OPEN GRIPPER</strong>
            <small>Mở kẹp</small>
          </div>
        </button>

        <button
          type="button"
          className="quick-btn btn-close-grip"
          onClick={() => send("CLOSE_GRIPPER")}
        >
          <span className="btn-icon">🔒</span>
          <div className="btn-text">
            <strong>CLOSE GRIPPER</strong>
            <small>Đóng kẹp</small>
          </div>
        </button>
      </div>
    </div>
  );
}
