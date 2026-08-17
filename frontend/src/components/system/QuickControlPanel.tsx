import { useState } from "react";

interface Props {
  onCommand?: (cmd: string, payload?: Record<string, unknown>) => void;
  systemMode?: "AUTO" | "MANUAL";
  robotState?: string;
  connected?: boolean;
  ipAddress?: string;
  port?: number;
  holdingProduct?: string | null;
  currentSlot?: string | null;
  servoOk?: boolean;
  brakeOk?: boolean;
}

export function QuickControlPanel({
  onCommand,
  systemMode = "AUTO",
  robotState = "IDLE",
  connected = true,
  ipAddress = "192.168.58.2",
  port = 8090,
  holdingProduct = null,
  currentSlot = null,
  servoOk = true,
  brakeOk = true,
}: Props) {
  const [selectedSlot, setSelectedSlot] = useState<string>("A2");

  const send = (cmd: string, payload?: Record<string, unknown>) => {
    if (onCommand) {
      onCommand(cmd, payload);
    }
  };

  return (
    <div className="hmi-card quick-control-panel robot-hmi-card">
      <div className="card-header flex-between">
        <div className="card-title-group">
          <h3>🤖 ROBOT FR3 STATUS</h3>
          <span className="card-subtitle">FAIRINO COBOT / LUA TCP PROTOCOL</span>
        </div>
        <span className={`connection-badge ${connected ? "online" : "offline"}`}>
          {connected ? "ONLINE ●" : "OFFLINE ●"}
        </span>
      </div>

      <div className="card-body robot-layout">
        {/* Permanent Robot Hardware Visual & Specs List (Visible in BOTH modes) */}
        <div className="robot-hardware-visual flex-between">
          {/* Fairino Industrial Controller Graphic */}
          <div className="robot-device-graphic">
            <div className="robot-brand-banner">
              <span className="fairino-brand">FAIRINO</span>
              <span className="robot-model font-mono">FR3 COBOT</span>
            </div>
            <div className="robot-cpu-body">
              <div className="cpu-door">
                <div className="led-row">
                  <div className="led-item">
                    <span className={`led ${servoOk && connected ? "led-run active" : "led-error"}`}></span> SERVO
                  </div>
                  <div className="led-item">
                    <span className={`led ${brakeOk && connected ? "led-run active" : "led-maint"}`}></span> BRAKE
                  </div>
                  <div className="led-item">
                    <span className={`led ${systemMode === "AUTO" ? "led-run active" : "led-maint"}`}></span> AUTO
                  </div>
                </div>
              </div>
              <div className="io-terminal-strip">
                <span className="term-pin active"></span>
                <span className="term-pin active"></span>
                <span className="term-pin active"></span>
                <span className="term-pin active"></span>
                <span className="term-pin active"></span>
              </div>
            </div>
          </div>

          {/* Robot Specs List */}
          <div className="robot-specs-list">
            <div className="spec-row flex-between">
              <span>Connection</span>
              <strong className={connected ? "text-green" : "text-red"}>
                {connected ? "ONLINE (SOCKET)" : "OFFLINE"}
              </strong>
            </div>
            <div className="spec-row flex-between">
              <span>IP Address</span>
              <strong className="font-mono text-cyan">{ipAddress}:{port}</strong>
            </div>
            <div className="spec-row flex-between">
              <span>Robot State</span>
              <strong className="font-mono text-green">{robotState || "IDLE"}</strong>
            </div>
            <div className="spec-row flex-between">
              <span>Holding Product</span>
              <strong className="font-mono text-cyan">{holdingProduct || "EMPTY"}</strong>
            </div>
            <div className="spec-row flex-between">
              <span>Target Station</span>
              <strong className="text-cyan font-mono">{currentSlot || "STANDBY"}</strong>
            </div>
          </div>
        </div>

        {/* Permanent 4 Indicator Boxes (Visible in BOTH modes) */}
        <div className="robot-indicators-row flex-between">
          <div className={`indicator-box ${systemMode === "AUTO" ? "active" : ""}`}>
            <span className="icon">🤖</span>
            <span className="label">Mode</span>
            <span className="value font-mono">{systemMode === "AUTO" ? "AUTO (FSM)" : "MANUAL"}</span>
          </div>

          <div className={`indicator-box ${holdingProduct ? "active" : ""}`}>
            <span className="icon">🖐️</span>
            <span className="label">Gripper</span>
            <span className="value font-mono">{holdingProduct ? "HOLDING" : "OPEN/READY"}</span>
          </div>

          <div className={`indicator-box ${currentSlot ? "active" : ""}`}>
            <span className="icon">📍</span>
            <span className="label">Target Pos</span>
            <span className="value font-mono">{currentSlot || "HOME"}</span>
          </div>

          <div className={`indicator-box ${servoOk ? "active-ok" : "active-error"}`}>
            <span className="icon">🛡️</span>
            <span className="label">Servo Safety</span>
            <span className="value font-mono">{servoOk ? "READY (OK)" : "ERROR"}</span>
          </div>
        </div>

        {/* Compact Manual Controls Toolbar (ONLY VISIBLE IN MANUAL MODE) */}
        {systemMode === "MANUAL" && (
          <div className="robot-manual-controls-section">
            <div className="manual-section-title flex-between">
              <span className="font-mono text-cyan">🎮 ĐIỀU KHIỂN THỦ CÔNG ROBOT:</span>
              <span className="mode-indicator-tag active-manual">MANUAL SẴN SÀNG</span>
            </div>

            {/* Row 1: Fixed Positions */}
            <div className="manual-btn-grid-3">
              <button
                type="button"
                className="btn-manual-plc"
                onClick={() => send("HOME")}
                title="Di chuyển Robot về vị trí Home an toàn"
              >
                🏠 Vị trí HOME
              </button>
              <button
                type="button"
                className="btn-manual-plc"
                onClick={() => send("STANDBY")}
                title="Di chuyển Robot về vị trí Chờ (Standby)"
              >
                ⏸️ Vị trí STANDBY
              </button>
              <button
                type="button"
                className="btn-manual-plc"
                onClick={() => send("SCAN_QR_POS")}
                title="Đưa hàng đến trước Camera QR CAM01"
              >
                📷 Vị trí Soi QR
              </button>
            </div>

            {/* Row 2: Warehouse Slot and UAV Pad Controls */}
            <div className="robot-manual-slot-row flex-between">
              <div className="slot-picker-compact flex-between">
                <span className="lbl-mini">Ô Kho:</span>
                <select
                  className="slot-selector-dropdown-inline"
                  value={selectedSlot}
                  onChange={(e) => setSelectedSlot(e.target.value)}
                >
                  {["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"].map((s) => (
                    <option key={s} value={s}>
                      Ô {s}
                    </option>
                  ))}
                </select>
              </div>

              <div className="slot-action-btn-group">
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-green"
                  onClick={() => send("PICK", { slot: selectedSlot })}
                  title={`Robot gắp sản phẩm tại ô kho ${selectedSlot}`}
                >
                  📤 Gắp Ô [{selectedSlot}]
                </button>
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-yellow"
                  onClick={() => send("STORE", { slot: selectedSlot })}
                  title={`Robot cất sản phẩm vào ô kho ${selectedSlot}`}
                >
                  📥 Thả Ô [{selectedSlot}]
                </button>
              </div>
            </div>

            {/* Row 3: UAV Pad N1 & Gripper Quick Actions */}
            <div className="manual-btn-grid-4">
              <button
                type="button"
                className="btn-manual-plc btn-uav-pick-btn"
                onClick={() => send("PICK_UAV")}
                title="Robot gắp kiện hàng từ lưng UAV tại bãi đáp N1"
              >
                🛬 Gắp Từ UAV
              </button>
              <button
                type="button"
                className="btn-manual-plc btn-uav-place-btn"
                onClick={() => send("PLACE_UAV")}
                title="Robot đặt kiện hàng lên lưng UAV tại bãi đáp N1"
              >
                🚀 Thả Lên UAV
              </button>
              <button
                type="button"
                className="btn-manual-plc"
                onClick={() => send("OPEN_GRIPPER")}
                title="Mở ngàm kẹp Robot"
              >
                🔓 Mở Kẹp
              </button>
              <button
                type="button"
                className="btn-manual-plc"
                onClick={() => send("CLOSE_GRIPPER")}
                title="Đóng ngàm kẹp Robot"
              >
                🔒 Đóng Kẹp
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
