import { useMemo } from "react";

export interface TaskStepItem {
  id: number;
  label: string;
  desc?: string;
  status: "completed" | "in_progress" | "pending";
}

export interface WaitingMissionItem {
  id: number;
  order_id?: number | null;
  mission_type: string;
  drone_id: string;
  product_id: string;
  target_slot?: string | null;
  status: string;
  priority?: number;
  created_at?: string;
}

export interface ActiveMissionInfo {
  id: number;
  order_id?: number | null;
  mission_type: string; // "DRONE_PICKUP" | "DRONE_DELIVERY" | string
  drone_id: string;
  product_id: string;
  target_slot?: string | null;
  status: string;
  current_phase?: string;
  step_details?: string;
}

interface Props {
  activeMission?: ActiveMissionInfo | null;
  stationOpStep?: string | null;
  stationOpDetails?: string | null;
  waitingQueue?: WaitingMissionItem[];
  progressPercent?: number;
  autoState?: "STANDBY" | "RUNNING" | "PAUSED" | string;
  systemMode?: "AUTO" | "MANUAL" | string;
  onStartAuto?: () => void;
}

export function TaskMonitor({
  activeMission,
  stationOpStep,
  stationOpDetails,
  waitingQueue = [],
  progressPercent,
  autoState = "STANDBY",
  systemMode = "AUTO",
  onStartAuto,
}: Props) {
  const isPickup =
    !activeMission ||
    activeMission.mission_type === "DRONE_PICKUP" ||
    activeMission.mission_type === "INBOUND" ||
    activeMission.mission_type.includes("PICKUP");

  const missionTypeLabel = isPickup ? "📥 NHẬN HÀNG (INBOUND)" : "📤 GIAO HÀNG (OUTBOUND)";
  const targetSlot = activeMission?.target_slot || "A2";
  const droneId = activeMission?.drone_id || "UAV-01";
  const productId = activeMission?.product_id || (activeMission ? `PRD-100${activeMission.id}` : "PRD-1001");

  // Determine current active step index (0 to 5)
  const currentStepIndex = useMemo(() => {
    if (!activeMission) return -1;
    if (activeMission.status === "COMPLETED") return 6; // All completed

    const phase = (activeMission.current_phase || "").toUpperCase();
    const details = (activeMission.step_details || stationOpDetails || "").toUpperCase();
    const step = (stationOpStep || "").toUpperCase();

    if (isPickup) {
      // Inbound steps:
      // 0: UAV Land
      // 1: PLC Lock & Z-Down
      // 2: Robot Pick from UAV
      // 3: QR Scan
      // 4: Store in Slot
      // 5: Robot Home / Done
      if (details.includes("HOME") || details.includes("HOÀN TẤT") || phase.includes("DONE")) return 5;
      if (details.includes("STORE") || details.includes("CẤT") || step.includes("STORE")) return 4;
      if (details.includes("QR") || details.includes("SCAN") || details.includes("SOI")) return 3;
      if (details.includes("PICK") || details.includes("GẮP") || step.includes("PICK")) return 2;
      if (details.includes("PLC") || details.includes("LOCK") || details.includes("KHÓA") || details.includes("Z-DOWN")) return 1;
      return 0; // UAV Landed / Landing
    } else {
      // Outbound steps:
      // 0: Robot Pick from Slot
      // 1: QR Verification
      // 2: Place on UAV Pad N1
      // 3: PLC Z-Up & Release
      // 4: UAV Takeoff & Deliver
      // 5: Robot Home / Ready
      if (details.includes("HOME") || details.includes("READY") || phase.includes("DONE")) return 5;
      if (details.includes("TAKEOFF") || details.includes("BAY") || details.includes("DELIVER")) return 4;
      if (details.includes("PLC") || details.includes("Z-UP") || details.includes("MỞ NGÀM")) return 3;
      if (details.includes("PLACE") || details.includes("ĐẶT") || step.includes("PLACE")) return 2;
      if (details.includes("QR") || details.includes("SCAN") || details.includes("SOI")) return 1;
      return 0; // Robot Pick from Slot
    }
  }, [activeMission, isPickup, stationOpStep, stationOpDetails]);

  // Generate 6 visual steps according to mission type
  const steps: TaskStepItem[] = useMemo(() => {
    if (isPickup) {
      const labels = [
        { id: 1, label: "1. UAV tiếp cận & đáp bãi Pad N1", desc: `${droneId} hạ cánh chính xác` },
        { id: 2, label: "2. PLC khóa ngàm Drone & hạ trục Z", desc: "Cố định UAV an toàn" },
        { id: 3, label: "3. Robot gắp kiện hàng từ lưng UAV", desc: "Robot FR3 gắp kiện hàng" },
        { id: 4, label: "4. Robot đưa hàng soi mã QR CAM01", desc: "Xác thực mã vạch sản phẩm" },
        { id: 5, label: `5. Robot cất hàng vào Ô Kho [${targetSlot}]`, desc: `Lưu trữ vào ô ${targetSlot}` },
        { id: 6, label: "6. Robot về Home / Hoàn tất nhận hàng", desc: "Quy trình kết thúc thành công" },
      ];

      return labels.map((l, idx) => {
        let status: "completed" | "in_progress" | "pending" = "pending";
        if (currentStepIndex === -1) {
          status = "pending";
        } else if (idx < currentStepIndex) {
          status = "completed";
        } else if (idx === currentStepIndex) {
          status = "in_progress";
        } else {
          status = "pending";
        }
        return { ...l, status };
      });
    } else {
      const labels = [
        { id: 1, label: `1. Robot gắp hàng từ Ô Kho [${targetSlot}]`, desc: `Lấy kiện hàng tại ô ${targetSlot}` },
        { id: 2, label: "2. Robot quét mã QR kiểm tra hàng", desc: "Kiểm tra đúng mã đơn hàng" },
        { id: 3, label: "3. Robot đặt kiện hàng lên lưng UAV N1", desc: `Gắn hàng lên lưng ${droneId}` },
        { id: 4, label: "4. PLC nâng trục Z & mở ngàm sẵn sàng", desc: "Mở khóa cất cánh" },
        { id: 5, label: "5. UAV cất cánh rời trạm đi giao hàng", desc: `${droneId} bay giao điểm hẹn` },
        { id: 6, label: "6. Robot & Trạm về trạng thái Chờ (Ready)", desc: "Sẵn sàng nhận đơn kế tiếp" },
      ];

      return labels.map((l, idx) => {
        let status: "completed" | "in_progress" | "pending" = "pending";
        if (currentStepIndex === -1) {
          status = "pending";
        } else if (idx < currentStepIndex) {
          status = "completed";
        } else if (idx === currentStepIndex) {
          status = "in_progress";
        } else {
          status = "pending";
        }
        return { ...l, status };
      });
    }
  }, [isPickup, currentStepIndex, targetSlot, droneId]);

  // Calculate dynamic progress percent
  const calculatedProgress = useMemo(() => {
    if (progressPercent !== undefined && progressPercent !== null) return progressPercent;
    if (!activeMission) return 0;
    if (activeMission.status === "COMPLETED") return 100;
    if (currentStepIndex >= 0) {
      return Math.min(100, Math.round(((currentStepIndex + 0.5) / 6) * 100));
    }
    return 15;
  }, [progressPercent, activeMission, currentStepIndex]);

  return (
    <div className="hmi-card task-monitor-card dynamic-task-monitor">
      {/* Header */}
      <div className="card-header flex-between">
        <div className="card-title-group">
          <h3>📋 GIÁM SÁT ĐƠN HÀNG & TIẾN ĐỘ</h3>
          <span className="card-subtitle">WORKFLOW STEPPER & FIFO QUEUE</span>
        </div>
        {activeMission ? (
          <span className={`mission-type-pill ${isPickup ? "pill-pickup" : "pill-delivery"}`}>
            {missionTypeLabel}
          </span>
        ) : autoState === "RUNNING" ? (
          <span className="mission-type-pill pill-pickup">⚡ ĐANG ĐIỀU PHỐI</span>
        ) : (
          <span className="mission-type-pill pill-standby">💤 CHẾ ĐỘ CHỜ</span>
        )}
      </div>

      <div className="card-body task-monitor-layout">
        {/* Section 1: Active Order Hero Card */}
        {activeMission ? (
          <div className="active-order-hero-box">
            <div className="order-main-header flex-between">
              <div className="order-title-info">
                <span className="order-badge-id font-mono">
                  #{activeMission.order_id ? `ORD-${activeMission.order_id}` : `MISSION-${activeMission.id}`}
                </span>
                <strong className="order-product-name">Sản phẩm: {productId}</strong>
              </div>
              <div className="order-progress-tag font-mono">
                Tiến độ: <strong className="text-cyan">{calculatedProgress}%</strong>
              </div>
            </div>

            {/* Key Mission Attributes Bar */}
            <div className="order-specs-bar flex-between">
              <div className="spec-pill">
                <span className="lbl">Loại đơn:</span>
                <strong className={isPickup ? "text-green" : "text-amber"}>
                  {isPickup ? "Nhận Hàng (Inbound)" : "Giao Hàng (Outbound)"}
                </strong>
              </div>
              <div className="spec-pill">
                <span className="lbl">Ô Kho Target:</span>
                <strong className="text-cyan font-mono">Ô [{targetSlot}]</strong>
              </div>
              <div className="spec-pill">
                <span className="lbl">Drone:</span>
                <strong className="text-purple font-mono">{droneId}</strong>
              </div>
              <div className="spec-pill">
                <span className="lbl">Trạng thái:</span>
                <span className="pulse-dot-cyan"></span>
                <strong className="text-cyan">{activeMission.status || "RUNNING"}</strong>
              </div>
            </div>

            {/* Neon Animated Progress Bar */}
            <div className="progress-bar-bg main-progress-neon">
              <div
                className="progress-bar-fill animated-stripes-neon"
                style={{ width: `${calculatedProgress}%` }}
              ></div>
            </div>

            {/* Stepper Steps List (6 Visual Steps) */}
            <div className="task-stepper-container">
              <div className="stepper-section-title font-mono text-cyan">
                Quy trình thực hiện ({isPickup ? "Nhận hàng vào kho" : "Giao hàng từ kho"}):
              </div>

              <div className="task-stepper-list-6">
                {steps.map((st) => (
                  <div key={`step-${st.id}`} className={`stepper-item-compact ${st.status}`}>
                    <div className="stepper-icon-badge">
                      {st.status === "completed" && <span className="icon-done">✓</span>}
                      {st.status === "in_progress" && <span className="icon-pulse">🔵</span>}
                      {st.status === "pending" && <span className="icon-pending">○</span>}
                    </div>
                    <div className="stepper-text-col">
                      <span className="stepper-label-bold">{st.label}</span>
                      <small className="stepper-desc-text">{st.desc}</small>
                    </div>
                    <span className="stepper-badge-state">
                      {st.status === "completed" && "Hoàn thành ✓"}
                      {st.status === "in_progress" && "Đang xử lý..."}
                      {st.status === "pending" && "Chờ"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="empty-task-standby-box">
            <span className="standby-icon">{autoState === "RUNNING" ? "⚡" : "💤"}</span>
            <div className="standby-text">
              <h4>
                {autoState === "RUNNING"
                  ? "HỆ THỐNG ĐANG TỰ ĐỘNG ĐIỀU PHỐI (RUNNING)"
                  : autoState === "PAUSED"
                  ? "HỆ THỐNG ĐANG TẠM DỪNG (PAUSED)"
                  : "HỆ THỐNG ĐANG Ở CHẾ ĐỘ CHỜ (STANDBY)"}
              </h4>
              <p>
                {autoState === "RUNNING"
                  ? "Hệ thống đang chuẩn bị kích hoạt đơn hàng tiếp theo từ hàng chờ FIFO."
                  : autoState === "PAUSED"
                  ? "Hàng chờ tự động đang tạm dừng. Bấm nút Khởi động bên dưới để tiếp tục điều phối."
                  : `Hàng chờ FIFO đang có ${waitingQueue.length} đơn hàng. Bấm nút Khởi động để bắt đầu chu trình tự động.`}
              </p>
              {autoState !== "RUNNING" && systemMode === "AUTO" && onStartAuto && (
                <button
                  type="button"
                  className="btn-start-auto-mini"
                  onClick={onStartAuto}
                  title="Bắt đầu chạy tự động toàn bộ kho trạm và điều phối đơn hàng FIFO"
                >
                  ⚡ KHỞI ĐỘNG CHẠY TỰ ĐỘNG (START AUTO)
                </button>
              )}
            </div>
          </div>
        )}

        {/* Section 2: Next Orders Queue (FIFO) */}
        <div className="next-orders-queue-section">
          <div className="queue-section-header flex-between">
            <span className="queue-title font-mono">
              ⏳ DANH SÁCH ĐƠN HÀNG TIẾP THEO (HÀNG CHỜ FIFO: {waitingQueue.length})
            </span>
            <span
              className={`queue-mode-tag ${
                systemMode === "MANUAL"
                  ? "tag-manual"
                  : autoState === "RUNNING"
                  ? "tag-running"
                  : "tag-standby"
              }`}
            >
              {systemMode === "MANUAL"
                ? "🎮 ĐIỀU KHIỂN THỦ CÔNG"
                : autoState === "RUNNING"
                ? "⚡ TỰ ĐỘNG DISPATCH (RUNNING)"
                : "💤 CHỜ KHỞI ĐỘNG (STANDBY)"}
            </span>
          </div>

          {waitingQueue.length === 0 ? (
            <div className="empty-queue-mini">
              <span>✨ Hàng chờ đang trống. Không có đơn hàng nào đang đợi.</span>
            </div>
          ) : (
            <div className="next-orders-list">
              {waitingQueue.slice(0, 3).map((item, idx) => {
                const itemIsPickup =
                  item.mission_type === "DRONE_PICKUP" ||
                  item.mission_type === "INBOUND" ||
                  item.mission_type.includes("PICKUP");

                return (
                  <div key={`queue-${item.id}`} className="next-order-card flex-between">
                    <div className="order-rank font-mono">#{idx + 1}</div>
                    <div className="order-meta-col">
                      <div className="order-top-row">
                        <span className="order-code font-mono">
                          #{item.order_id ? `ORD-${item.order_id}` : `MISSION-${item.id}`}
                        </span>
                        <span className={`order-type-badge-mini ${itemIsPickup ? "badge-in" : "badge-out"}`}>
                          {itemIsPickup ? "📥 Nhận Hàng" : "📤 Giao Hàng"}
                        </span>
                      </div>
                      <div className="order-sub-row">
                        <span>SP: <strong className="text-cyan">{item.product_id}</strong></span>
                        <span>· Đích: <strong>Ô [{item.target_slot || "A1"}]</strong></span>
                        <span>· UAV: <strong>{item.drone_id}</strong></span>
                      </div>
                    </div>
                    <div className="order-status-pill">
                      <span className="pulse-dot-amber"></span>
                      <span>Chờ lượt</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
