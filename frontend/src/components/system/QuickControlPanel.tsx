import { useState, memo } from "react";

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
  currentZLevel?: number;
  zInPosition?: boolean;
  selectedSlot?: string;
  onSelectSlot?: (slot: string) => void;
}

const SLOT_Z_LEVELS: Record<string, number> = {
  A1: 1, A2: 1, A3: 1,
  B1: 2, B2: 2, B3: 2,
  N1: 3, DOCK: 3, PAD: 3,
  O1: 4, CONVEYOR: 4,
};

const Z_LEVEL_TITLES: Record<number, string> = {
  0: "HOME (0)",
  1: "TẦNG A (1)",
  2: "TẦNG B (2)",
  3: "DRONE N1 (3)",
  4: "BĂNG TẢI O1 (4)",
};

export const QuickControlPanel = memo(function QuickControlPanel({
  onCommand,
  systemMode = "AUTO",
  robotState = "IDLE",
  connected = true,
  ipAddress = "192.168.57.2",
  port = 8090,
  holdingProduct = null,
  currentSlot = null,
  servoOk = true,
  brakeOk = true,
  currentZLevel = 0,
  zInPosition = true,
  selectedSlot: propSelectedSlot,
  onSelectSlot,
}: Props) {
  const [internalSlot, setInternalSlot] = useState<string>("A2");
  const selectedSlot = propSelectedSlot || internalSlot;

  const handleSelectSlot = (slot: string) => {
    setInternalSlot(slot);
    if (onSelectSlot) {
      onSelectSlot(slot);
    }
  };

  const requiredZ = SLOT_Z_LEVELS[selectedSlot] ?? 1;
  const isZAligned = currentZLevel === requiredZ && zInPosition;

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
              <strong className="text-cyan font-mono">{currentSlot || "HOME"}</strong>
            </div>
            <div className="spec-row flex-between">
              <span>Interlock DO0</span>
              <strong className={(!currentSlot || currentSlot === "HOME") ? "text-green font-mono" : "text-yellow font-mono"}>
                {(!currentSlot || currentSlot === "HOME") ? "DO0 = 1 (AN TOÀN HOME)" : "DO0 = 0 (RỜI HOME)"}
              </strong>
            </div>
          </div>
        </div>

        {/* Symmetrical 6-Box Robot Status Indicators Grid */}
        <div className="robot-indicators-row">
          {/* 1. Mode */}
          <div className={`indicator-box ${systemMode === "AUTO" ? "active" : "active-warn"}`} title="Chế độ hoạt động hiện tại">
            <span className="icon">🤖</span>
            <span className="label">Chế Độ</span>
            <span className="value font-mono">{systemMode === "AUTO" ? "AUTO (FSM)" : "MANUAL"}</span>
          </div>

          {/* 2. Gripper */}
          <div className={`indicator-box ${holdingProduct ? "active-ok" : ""}`} title="Trạng thái ngàm kẹp Robot">
            <span className="icon">🖐️</span>
            <span className="label">Tay Kẹp</span>
            <span className="value font-mono">{holdingProduct ? "KẸP HÀNG" : "MỞ SẴN SÀNG"}</span>
          </div>

          {/* 3. Target Position */}
          <div className="indicator-box active-ok" title="Vị trí trạm / ô kho hiện tại">
            <span className="icon">📍</span>
            <span className="label">Vị Trí</span>
            <span className="value font-mono">{currentSlot || "HOME"}</span>
          </div>

          {/* 4. Servo Safety */}
          <div className={`indicator-box ${servoOk && brakeOk ? "active" : "active-error"}`} title="Trạng thái động cơ Servo & Phanh">
            <span className="icon">🛡️</span>
            <span className="label">Servo & Phanh</span>
            <span className="value font-mono">{servoOk && brakeOk ? "READY (OK)" : "ERROR"}</span>
          </div>

          {/* 5. DO0 Home Signal (Interlock with PLC) */}
          <div
            className={`indicator-box ${(!currentSlot || currentSlot === "HOME") ? "active" : "active-warn"}`}
            title="Tín hiệu DO0 xuất sang PLC báo Robot đang ở vị trí HOME an toàn cho phép nâng hạ trục Z"
          >
            <span className="icon">{(!currentSlot || currentSlot === "HOME") ? "🏠" : "🔄"}</span>
            <span className="label">DO0 Home Sig</span>
            <span className="value font-mono">{(!currentSlot || currentSlot === "HOME") ? "ON (AN TOÀN Z)" : "OFF (CHẠY)"}</span>
          </div>

          {/* 6. Socket TCP Status */}
          <div className={`indicator-box ${connected ? "active-ok" : "active-error"}`} title="Kết nối Socket TCP Port 8090">
            <span className="icon">📡</span>
            <span className="label">Socket 8090</span>
            <span className="value font-mono">{connected ? "ONLINE ●" : "OFFLINE ●"}</span>
          </div>
        </div>

        {/* Compact Manual Controls Toolbar (ONLY VISIBLE IN MANUAL MODE) */}
        {systemMode === "MANUAL" && (
          <div className="robot-manual-controls-section">
            <div className="manual-section-title">
              <span className="font-mono text-cyan">🎮 ĐIỀU KHIỂN THỦ CÔNG ROBOT (MANUAL OVERRIDE):</span>
              <span className="mode-indicator-tag active-manual">MANUAL SẴN SÀNG</span>
            </div>

            {/* Group 1: Macro / Fixed Positions */}
            <div className="manual-control-group">
              <div className="manual-group-label">
                <span>📍 VỊ TRÍ ĐỊNH VỊ CỐ ĐỊNH (MACRO POSITIONS):</span>
              </div>
              <div className="manual-btn-grid-4">
                <button
                  type="button"
                  className={`btn-manual-plc ${(!currentSlot || currentSlot === "HOME") ? "active-level" : ""}`}
                  onClick={() => send("MOVE_HOME")}
                  title="Di chuyển Robot về vị trí Home an toàn (Kích DO0=1 cho PLC nâng Z)"
                >
                  🏠 Về HOME (DO0=1)
                </button>
                <button
                  type="button"
                  className={`btn-manual-plc ${currentSlot === "STANDBY" ? "active-level" : ""}`}
                  onClick={() => send("STANDBY")}
                  title="Di chuyển Robot về vị trí Chờ (Standby)"
                >
                  ⏸️ Vị Trí STANDBY
                </button>
                <button
                  type="button"
                  className={`btn-manual-plc ${currentSlot === "SCAN_QR" ? "active-level" : ""}`}
                  onClick={() => send("SCAN_QR_POS")}
                  title="Đưa hàng đến trước Camera QR CAM01"
                >
                  📷 Vị Trí Soi QR
                </button>
                <button
                  type="button"
                  className={`btn-manual-plc ${currentSlot === "O1" ? "active-level" : ""}`}
                  onClick={() => send("PICK", { slot: "O1" })}
                  title="Di chuyển Robot đến vị trí đầu băng tải O1"
                >
                  🛞 Đầu Băng Tải O1
                </button>
              </div>
            </div>

            {/* Group 2: Storage Slots Selection & Pick/Store */}
            <div className="manual-control-group">
              <div className="manual-group-label">
                <span>📦 CHỌN Ô KHO HOẠT ĐỘNG (SLOTS A1..B3):</span>
              </div>
              {/* Slot selector chips */}
              <div className="slot-chips-grid">
                {["A1", "A2", "A3", "B1", "B2", "B3"].map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`slot-chip ${selectedSlot === s ? "active-slot-chip" : ""}`}
                    onClick={() => handleSelectSlot(s)}
                    title={`Chọn ô kho ${s}`}
                  >
                    Ô {s}
                  </button>
                ))}
              </div>

              {/* Safety Interlock Z Status Alert Badge (Cách B) */}
              <div
                style={{
                  margin: "8px 0",
                  padding: "6px 10px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  background: isZAligned ? "rgba(34, 197, 94, 0.12)" : "rgba(234, 179, 8, 0.12)",
                  border: isZAligned ? "1px solid rgba(34, 197, 94, 0.4)" : "1px solid rgba(234, 179, 8, 0.4)",
                  color: isZAligned ? "#22c55e" : "#eab308",
                }}
              >
                <span>{isZAligned ? "✅" : "⚠️"}</span>
                <span>
                  {isZAligned ? (
                    <>Trục Z đã sẵn sàng ở <strong>{Z_LEVEL_TITLES[requiredZ]}</strong>. Đủ điều kiện gửi lệnh Robot.</>
                  ) : (
                    <>Cần nhấn <strong>[{Z_LEVEL_TITLES[requiredZ]}]</strong> trên cụm PLC trước khi gắp/cất ô {selectedSlot}! (Hiện tại: {zInPosition ? Z_LEVEL_TITLES[currentZLevel] || `TẦNG ${currentZLevel}` : "ĐANG CHẠY..."})</>
                  )}
                </span>
              </div>

              <div className="manual-btn-grid-2">
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-green"
                  onClick={() => send("PICK", { slot: selectedSlot })}
                  title={`Robot gắp sản phẩm tại ô kho ${selectedSlot}`}
                >
                  📤 Gắp Từ Ô [{selectedSlot}]
                </button>
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-yellow"
                  onClick={() => send("STORE", { slot: selectedSlot })}
                  title={`Robot cất sản phẩm vào ô kho ${selectedSlot}`}
                >
                  📥 Cất Vào Ô [{selectedSlot}]
                </button>
              </div>
            </div>

            {/* Group 3: Drone Dock N1 */}
            <div className="manual-control-group">
              <div className="manual-group-label">
                <span>🚁 TƯƠNG TÁC BÃI ĐÁP DRONE DOCK N1:</span>
              </div>

              {/* Z-axis warning for Drone N1 (level 3) */}
              {(() => {
                const droneZ = SLOT_Z_LEVELS["N1"]; // = 3
                const isDroneZAligned = zInPosition && currentZLevel === droneZ;
                return (
                  <div className={`z-axis-hint ${isDroneZAligned ? "z-ok" : "z-warn"}`}>
                    <span>{isDroneZAligned ? "✅" : "⚠️"}</span>
                    <span>
                      {isDroneZAligned ? (
                        <>Trục Z đã sẵn sàng ở <strong>{Z_LEVEL_TITLES[droneZ]}</strong>. Đủ điều kiện gắp/đặt Drone.</>
                      ) : (
                        <>Cần nhấn <strong>🚁 Drone N1 ({droneZ})</strong> trên cụm PLC trước khi gắp/đặt tại Drone! (Hiện tại: {zInPosition ? Z_LEVEL_TITLES[currentZLevel] || `TẦNG ${currentZLevel}` : "ĐANG CHẠY..."})</>
                      )}
                    </span>
                  </div>
                );
              })()}

              <div className="manual-btn-grid-2">
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-cyan"
                  onClick={() => send("PICK_UAV")}
                  title="Robot gắp kiện hàng từ lưng UAV tại bãi đáp N1"
                >
                  🚁 Gắp Khỏi Drone N1
                </button>
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-cyan"
                  onClick={() => send("PLACE_UAV")}
                  title="Robot đặt kiện hàng lên lưng UAV tại bãi đáp N1"
                >
                  🚀 Đặt Lên Drone N1
                </button>
              </div>
            </div>

            {/* Group 3b: Băng Tải O1 */}
            <div className="manual-control-group">
              <div className="manual-group-label">
                <span>🛞 TƯƠNG TÁC BĂNG TẢI O1:</span>
              </div>

              {/* Z-axis warning for Băng Tải O1 (level 4) */}
              {(() => {
                const conveyorZ = SLOT_Z_LEVELS["O1"]; // = 4
                const isConveyorZAligned = zInPosition && currentZLevel === conveyorZ;
                return (
                  <div className={`z-axis-hint ${isConveyorZAligned ? "z-ok" : "z-warn"}`}>
                    <span>{isConveyorZAligned ? "✅" : "⚠️"}</span>
                    <span>
                      {isConveyorZAligned ? (
                        <>Trục Z đã sẵn sàng ở <strong>{Z_LEVEL_TITLES[conveyorZ]}</strong>. Đủ điều kiện gắp/đặt băng tải.</>
                      ) : (
                        <>Cần nhấn <strong>🛞 Băng Tải O1 ({conveyorZ})</strong> trên cụm PLC trước khi gắp/cất tại băng tải! (Hiện tại: {zInPosition ? Z_LEVEL_TITLES[currentZLevel] || `TẦNG ${currentZLevel}` : "ĐANG CHẠY..."})</>
                      )}
                    </span>
                  </div>
                );
              })()}

              <div className="manual-btn-grid-2">
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-yellow"
                  onClick={() => send("STORE", { slot: "O1" })}
                  title="Robot đặt kiện hàng xuống băng tải O1"
                >
                  📥 Đặt Lên Băng Tải O1
                </button>
                <button
                  type="button"
                  className="btn-manual-plc btn-plc-green"
                  onClick={() => send("PICK", { slot: "O1" })}
                  title="Robot gắp kiện hàng từ băng tải O1"
                >
                  📤 Gắp Từ Băng Tải O1
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});
