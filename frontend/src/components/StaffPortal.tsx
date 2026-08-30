import { useState, useEffect, useCallback } from "react";
import type { StorageSlot } from "../types/drone";
import {
  getStaffStatus,
  setStaffOperationMode,
  startStaffOutbound,
  cancelStaffOutbound,
  startStaffInbound,
  stopStaffInbound,
  getInventorySlots,
} from "../services/api";

interface StaffPortalProps {
  storageSlots?: StorageSlot[];
  onRefreshStorage?: () => void;
}

interface StaffOperationState {
  active_type: "OUTBOUND" | "INBOUND" | null;
  status: "IDLE" | "RUNNING" | "PAUSED" | "COMPLETED" | "CANCELLED" | "ERROR";
  message: string;
  outbound: {
    queue: string[];
    completed: string[];
    current_slot: string | null;
    total: number;
    remaining: number;
  };
  inbound: {
    mode: "QUANTITY" | "MANUAL" | "FULL_AUTO";
    target_count: number;
    current_count: number;
    current_slot: string | null;
    last_scanned_qr: string | null;
  };
  robot_state: string;
  plc_state: {
    connected: boolean;
    busy: boolean;
  };
}

interface SystemModeState {
  mode: string;
  auto_state: string;
  operation_mode: "STATION_AUTO" | "STAFF_OPERATION";
  is_staff_mode: boolean;
  is_auto_running: boolean;
}

export function StaffPortal({ storageSlots: propStorageSlots, onRefreshStorage }: StaffPortalProps) {
  // Mode & Tabs
  const [activeSubTab, setActiveSubTab] = useState<"outbound" | "inbound">("outbound");
  const [sysMode, setSysMode] = useState<SystemModeState>({
    mode: "AUTO",
    auto_state: "STANDBY",
    operation_mode: "STAFF_OPERATION",
    is_staff_mode: true,
    is_auto_running: false,
  });

  const [staffOp, setStaffOp] = useState<StaffOperationState>({
    active_type: null,
    status: "IDLE",
    message: "Sẵn sàng nhận lệnh.",
    outbound: { queue: [], completed: [], current_slot: null, total: 0, remaining: 0 },
    inbound: { mode: "QUANTITY", target_count: 1, current_count: 0, current_slot: null, last_scanned_qr: null },
    robot_state: "IDLE",
    plc_state: { connected: true, busy: false },
  });

  // Local storage slots state
  const [localSlots, setLocalSlots] = useState<StorageSlot[]>(propStorageSlots || []);

  // Outbound Form state
  const [outboundMode, setOutboundMode] = useState<"QUANTITY" | "SLOTS">("QUANTITY");
  const [outboundQuantity, setOutboundQuantity] = useState<number>(3);
  const [selectedSlotsToPick, setSelectedSlotsToPick] = useState<string[]>([]);

  // Inbound Form state (Continuous mode)

  // Status message / notifications
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch live state from backend
  const fetchStatus = useCallback(async () => {
    try {
      const [res, slotsRes] = await Promise.all([
        getStaffStatus().catch(() => null),
        getInventorySlots().catch(() => null),
      ]);

      if (res && res.ok) {
        const data = await res.json();
        if (data.system_mode) setSysMode(data.system_mode);
        if (data.staff_op) setStaffOp(data.staff_op);
      }

      if (slotsRes && slotsRes.ok) {
        const slotsData = await slotsRes.json();
        setLocalSlots(slotsData);
      }
    } catch {
      // silent polling error
    }
  }, []);

  // Poll state every 1.5s
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 1500);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Sync prop slots if passed
  useEffect(() => {
    if (propStorageSlots && propStorageSlots.length > 0) {
      setLocalSlots(propStorageSlots);
    }
  }, [propStorageSlots]);


  // Toggle slot selection for Outbound
  const handleSlotClick = (slotName: string, isOccupied: boolean) => {
    if (activeSubTab !== "outbound") return;
    if (staffOp.status === "RUNNING") return; // cannot modify queue during active run

    if (!isOccupied && !selectedSlotsToPick.includes(slotName)) {
      setActionError(`Ô ${slotName} hiện đang trống, không có hàng để lấy.`);
      return;
    }
    setActionError(null);

    setSelectedSlotsToPick((prev) =>
      prev.includes(slotName) ? prev.filter((s) => s !== slotName) : [...prev, slotName]
    );
  };

  // Start Outbound Action
  const handleStartOutbound = async () => {
    if (outboundMode === "SLOTS" && selectedSlotsToPick.length === 0) {
      setActionError("Vui lòng chọn ít nhất một ô có hàng để lấy.");
      return;
    }
    setLoading(true);
    setActionError(null);
    try {
      if (!isStaffModeActive) {
        await setStaffOperationMode("STAFF_OPERATION");
      }
      const res = await startStaffOutbound(
        outboundMode === "SLOTS" ? selectedSlotsToPick : undefined,
        outboundMode === "QUANTITY" ? outboundQuantity : undefined
      );
      if (res.ok) {
        setActionSuccess(
          outboundMode === "SLOTS"
            ? `Đã gửi xuống PLC lấy ${selectedSlotsToPick.length} sản phẩm theo ô chỉ định.`
            : `Đã gửi xuống PLC mục tiêu lấy ${outboundQuantity} sản phẩm ra băng tải.`
        );
        setSelectedSlotsToPick([]);
        fetchStatus();
        if (onRefreshStorage) onRefreshStorage();
      } else {
        const err = await res.json();
        setActionError(err.detail || "Không thể bắt đầu lấy hàng");
      }
    } catch (e: any) {
      setActionError(e.message || "Lỗi kết nối máy chủ");
    } finally {
      setLoading(false);
    }
  };

  // Cancel Outbound Action
  const handleCancelOutbound = async () => {
    setLoading(true);
    try {
      const res = await cancelStaffOutbound();
      if (res.ok) {
        setActionSuccess("Đã hủy tiến trình lấy hàng.");
        fetchStatus();
      }
    } catch (e: any) {
      setActionError(e.message || "Lỗi khi hủy");
    } finally {
      setLoading(false);
    }
  };

  // Start Inbound Action (Continuous Mode)
  const handleStartInbound = async () => {
    setLoading(true);
    setActionError(null);
    try {
      if (!isStaffModeActive) {
        await setStaffOperationMode("STAFF_OPERATION");
      }
      const res = await startStaffInbound();
      if (res.ok) {
        setActionSuccess("Đã bắt đầu nạp hàng chủ động (Liên tục: Tự kết thúc khi đầy kho hoặc bấm Kết Thúc).");
        fetchStatus();
        if (onRefreshStorage) onRefreshStorage();
      } else {
        const err = await res.json();
        setActionError(err.detail || "Không thể bắt đầu nạp hàng");
      }
    } catch (e: any) {
      setActionError(e.message || "Lỗi kết nối máy chủ");
    } finally {
      setLoading(false);
    }
  };

  // Stop Inbound Action
  const handleStopInbound = async () => {
    setLoading(true);
    try {
      const res = await stopStaffInbound();
      if (res.ok) {
        setActionSuccess("Đã kết thúc nạp hàng.");
        fetchStatus();
      }
    } catch (e: any) {
      setActionError(e.message || "Lỗi khi dừng");
    } finally {
      setLoading(false);
    }
  };

  const isStaffModeActive = sysMode.operation_mode === "STAFF_OPERATION";
  const isRunning = staffOp.status === "RUNNING";

  return (
    <div className="staff-portal-container">
      {/* Top Banner: Mode Switcher */}
      <div className="staff-header-banner">
        <div className="banner-left">
          <div className="banner-title">
            <span className="portal-icon">👨‍💼</span>
            <div>
              <h2>TRUNG TÂM VẬN HÀNH KHO NHÂN VIÊN</h2>
              <p className="portal-subtitle">Điều khiển Băng tải, Vị trí nạp O1 và Xuất/Nhập Ma trận Kho 3x3</p>
            </div>
          </div>
        </div>

        <div className="banner-right">
          <div className="staff-mode-badge-box">
            <span className="mode-badge-label">PHÂN HỆ VẬN HÀNH:</span>
            <div className={`mode-status-pill ${isRunning ? "pill-running" : isStaffModeActive ? "pill-staff" : "pill-station"}`}>
              <span className="pulse-dot"></span>
              <span className="mode-status-text">
                {isRunning
                  ? `⚡ ĐANG XỬ LÝ (${staffOp.active_type === "OUTBOUND" ? "XUẤT BĂNG TẢI" : "NẠP VÀO KHO"})`
                  : isStaffModeActive
                  ? "👨‍💼 NHÂN VIÊN KHO (SẴN SÀNG)"
                  : "🚁 ĐANG ƯU TIÊN KHO TRẠM AUTO"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Alerts */}
      {actionError && <div className="staff-alert error">❌ {actionError}</div>}
      {actionSuccess && <div className="staff-alert success">✅ {actionSuccess}</div>}

      {sysMode.is_auto_running && (
        <div className="staff-notice-banner warning">
          ⚠️ Trạm đang trong chu trình tự động phục vụ Drone (Auto Running). Vui lòng bấm <strong>TẠM DỪNG</strong> trên thanh Header chính trước khi thực hiện lấy/thêm hàng.
        </div>
      )}

      {/* Main Grid: Left (3x3 Matrix + Conveyor) & Right (Operations Form) */}
      <div className="staff-main-grid">
        {/* Left Column: 3x3 Warehouse Interactive Matrix & Conveyor Visual */}
        <div className="staff-left-column">
          <div className="card-panel warehouse-matrix-card">
            <div className="card-header">
              <h3>📦 Sơ đồ 9 Ô Chứa Hàng (A1 - C3)</h3>
              <span className="card-hint">
                {activeSubTab === "outbound"
                  ? "Click vào ô có hàng để chọn lấy ra băng tải"
                  : "Hiển thị trạng thái ô trống / ô có hàng"}
              </span>
            </div>

            {/* 3x3 Interactive Grid */}
            <div className="staff-grid-3x3">
              {["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"].map((slotName) => {
                const slotData = localSlots.find((s) => s.slot_name === slotName);
                const isOccupied = slotData?.status === "OCCUPIED" || Boolean(slotData?.product_id);
                const isSelected = selectedSlotsToPick.includes(slotName);
                const isCurrentOp =
                  (staffOp.active_type === "OUTBOUND" && staffOp.outbound.current_slot === slotName) ||
                  (staffOp.active_type === "INBOUND" && staffOp.inbound.current_slot === slotName);

                return (
                  <div
                    key={slotName}
                    className={`staff-slot-box ${isOccupied ? "occupied" : "empty"} ${
                      isSelected ? "selected-pick" : ""
                    } ${isCurrentOp ? "active-motion" : ""}`}
                    onClick={() => handleSlotClick(slotName, isOccupied)}
                  >
                    <div className="slot-badge-top">
                      <span className="slot-name">{slotName}</span>
                      <span className={`slot-dot ${isOccupied ? "dot-full" : "dot-empty"}`} />
                    </div>

                    <div className="slot-content">
                      {isCurrentOp ? (
                        <div className="slot-motion-tag">🤖 ĐANG GẮP...</div>
                      ) : isOccupied ? (
                        <>
                          <div className="slot-prod-id">{slotData?.product_id || "SP_KHO"}</div>
                          <div className="slot-qr-tag">{slotData?.qr_code || "MÃ QR"}</div>
                        </>
                      ) : (
                        <div className="slot-empty-tag">Ô TRỐNG</div>
                      )}
                    </div>

                    {isSelected && activeSubTab === "outbound" && (
                      <div className="slot-pick-indicator">✓ ĐÃ CHỌN</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Conveyor Realtime Status Card */}
          <div className="card-panel conveyor-status-card">
            <div className="card-header">
              <h3>🔄 Trạng Thái Băng Tải & Điểm Nạp O1</h3>
              <span className={`badge ${isRunning ? "badge-running" : "badge-idle"}`}>
                {isRunning ? "ĐANG HOẠT ĐỘNG" : "STANDBY"}
              </span>
            </div>

            <div className="conveyor-visualizer">
              {/* Sensor 1 (Robot Head) */}
              <div className="conveyor-sensor-node">
                <div className={`sensor-bulb ${staffOp.outbound.current_slot ? "sensor-active" : ""}`} />
                <span className="sensor-title">Cảm Biến 1 (Đầu Băng Tải / O1)</span>
                <span className="sensor-role">Vị trí Robot gắp / thả</span>
              </div>

              {/* Animated Conveyor Track */}
              <div className="conveyor-track-wrapper">
                <div className={`conveyor-belt ${isRunning ? "conveyor-moving" : ""}`}>
                  <div className="belt-line" />
                  <div className="belt-line" />
                  <div className="belt-line" />
                  <div className="belt-line" />
                  <div className="belt-line" />
                </div>
                <div className="conveyor-direction">
                  {staffOp.active_type === "OUTBOUND" ? "➡️ Hướng xuất ra Nhân viên" : "⬅️ Hướng nhập vào Robot"}
                </div>
              </div>

              {/* Sensor 2 (Staff End) */}
              <div className="conveyor-sensor-node">
                <div className="sensor-bulb" />
                <span className="sensor-title">Cảm Biến 2 (Cuối Băng Tải)</span>
                <span className="sensor-role">Vị trí Nhân viên nhận hàng</span>
              </div>
            </div>

            {/* Hardware Quick Indicators */}
            <div className="hardware-pill-row">
              <div className="hardware-pill">
                <span className="pill-lbl">Robot State:</span>
                <span className="pill-val highlight">{staffOp.robot_state}</span>
              </div>
              <div className="hardware-pill">
                <span className="pill-lbl">PLC Connect:</span>
                <span className={`pill-val ${staffOp.plc_state.connected ? "green" : "red"}`}>
                  {staffOp.plc_state.connected ? "ONLINE" : "OFFLINE"}
                </span>
              </div>
              <div className="hardware-pill">
                <span className="pill-lbl">Camera QR:</span>
                <span className="pill-val green">SẴN SÀNG</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Operations Panel (Tabs: Lấy Hàng / Thêm Hàng) */}
        <div className="staff-right-column">
          <div className="card-panel operations-card">
            {/* Sub-Tabs Selector */}
            <div className="op-sub-tabs">
              <button
                type="button"
                className={`op-tab-btn ${activeSubTab === "outbound" ? "active" : ""}`}
                onClick={() => setActiveSubTab("outbound")}
                disabled={isRunning}
              >
                📦 1. LẤY HÀNG (OUTBOUND)
              </button>
              <button
                type="button"
                className={`op-tab-btn ${activeSubTab === "inbound" ? "active" : ""}`}
                onClick={() => setActiveSubTab("inbound")}
                disabled={isRunning}
              >
                📥 2. THÊM HÀNG (INBOUND)
              </button>
            </div>

            {/* TAB 1: LẤY HÀNG (OUTBOUND) */}
            {activeSubTab === "outbound" && (
              <div className="op-tab-content">
                <div className="op-section-desc">
                  Chọn các ô sản phẩm từ ma trận 9 ô bên trái, sau đó bấm <strong>BẮT ĐẦU LẤY HÀNG</strong> để Robot lần lượt gắp hàng ra băng tải cho nhân viên.
                </div>

                {/* Outbound Options */}
                <div className="inbound-options-group">
                  <h4>Chọn Chế Độ Lấy Hàng:</h4>
                  <div className="radio-options">
                    <label className={`radio-label ${outboundMode === "QUANTITY" ? "active" : ""}`}>
                      <input
                        type="radio"
                        name="outboundMode"
                        value="QUANTITY"
                        checked={outboundMode === "QUANTITY"}
                        onChange={() => setOutboundMode("QUANTITY")}
                        disabled={isRunning}
                      />
                      <div>
                        <strong>Theo số lượng (PLC đếm)</strong>
                      </div>
                    </label>

                    <label className={`radio-label ${outboundMode === "SLOTS" ? "active" : ""}`}>
                      <input
                        type="radio"
                        name="outboundMode"
                        value="SLOTS"
                        checked={outboundMode === "SLOTS"}
                        onChange={() => setOutboundMode("SLOTS")}
                        disabled={isRunning}
                      />
                      <div>
                        <strong>Chọn ô cụ thể</strong>
                      </div>
                    </label>
                  </div>
                </div>

                {outboundMode === "QUANTITY" && (
                  <div className="quantity-input-row">
                    <label>Số lượng kiện cần lấy:</label>
                    <input
                      type="number"
                      min={1}
                      max={9}
                      value={outboundQuantity}
                      onChange={(e) => setOutboundQuantity(parseInt(e.target.value) || 1)}
                      disabled={isRunning}
                      className="input-number"
                    />
                  </div>
                )}

                {/* Selected Queue Display */}
                {outboundMode === "SLOTS" && (
                  <div className="pick-queue-container">
                    <div className="queue-header">
                      <h4>Danh Sách Ô Cần Lấy ({selectedSlotsToPick.length} ô đã chọn):</h4>
                      {selectedSlotsToPick.length > 0 && !isRunning && (
                        <button
                          type="button"
                          className="btn-clear-queue"
                          onClick={() => setSelectedSlotsToPick([])}
                        >
                          Xóa chọn
                        </button>
                      )}
                    </div>

                    {selectedSlotsToPick.length === 0 && !isRunning ? (
                      <div className="empty-queue-msg">
                        Chưa chọn ô nào. Vui lòng click vào các ô màu xanh bên ma trận 3x3 để thêm vào danh sách lấy.
                      </div>
                    ) : (
                      <div className="queue-tags-list">
                        {selectedSlotsToPick.map((slot) => (
                          <span key={slot} className="queue-tag">
                            Ô {slot}
                            {!isRunning && (
                              <button
                                type="button"
                                className="tag-remove"
                                onClick={() => handleSlotClick(slot, true)}
                              >
                                ✕
                              </button>
                            )}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Progress Status if Running */}
                {staffOp.active_type === "OUTBOUND" && (
                  <div className="live-progress-box">
                    <div className="progress-header">
                      <span>Tiến độ lấy hàng:</span>
                      <strong>
                        {staffOp.outbound.completed.length} / {staffOp.outbound.total} ô hoàn tất
                      </strong>
                    </div>
                    <div className="progress-bar-bg">
                      <div
                        className="progress-bar-fill"
                        style={{
                          width: `${
                            staffOp.outbound.total > 0
                              ? (staffOp.outbound.completed.length / staffOp.outbound.total) * 100
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                    {staffOp.outbound.current_slot && (
                      <div className="current-slot-alert">
                        ⚡ Đang gắp ô: <strong>{staffOp.outbound.current_slot}</strong>
                      </div>
                    )}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="op-actions-row">
                  {!isRunning ? (
                    <button
                      type="button"
                      className="btn-primary-action btn-outbound"
                      onClick={handleStartOutbound}
                      disabled={loading || sysMode.is_auto_running || (outboundMode === "SLOTS" && selectedSlotsToPick.length === 0)}
                    >
                      🚀 BẮT ĐẦU LẤY HÀNG
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn-danger-action"
                      onClick={handleCancelOutbound}
                      disabled={loading}
                    >
                      🛑 HỦY LẤY HÀNG
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* TAB 2: THÊM HÀNG (INBOUND) */}
            {activeSubTab === "inbound" && (
              <div className="op-tab-content">
                <div className="op-section-desc">
                  <strong>Chế độ Nạp Chủ Động (Liên Tục):</strong> Nhân viên đặt hàng tại vị trí nạp <strong>O1</strong>. PLC phát hiện hàng qua cảm biến và kích tín hiệu <strong>DI3</strong> báo cho Robot tự động gắp vào các ô trống còn lại trong kho.
                  <br />
                  <span style={{ display: "inline-block", marginTop: "0.5rem", color: "#64748b" }}>
                    ℹ️ Chu trình hoạt động liên tục và <strong>tự động kết thúc khi ĐẦY KHO (9/9 ô)</strong> hoặc nhân viên có thể bấm <strong>KẾT THÚC THÊM HÀNG</strong> bất kỳ lúc nào.
                  </span>
                </div>

                {/* Live Inbound Progress */}
                {staffOp.active_type === "INBOUND" && (
                  <div className="live-progress-box inbound-box">
                    <div className="progress-header">
                      <span>Tiến trình nạp hàng:</span>
                      <strong>Đã nạp: {staffOp.inbound.current_count} kiện</strong>
                    </div>
                    {staffOp.inbound.current_slot && (
                      <div className="current-slot-alert">
                        📦 Robot đang cất vào ô: <strong>{staffOp.inbound.current_slot}</strong>
                      </div>
                    )}
                    {staffOp.inbound.last_scanned_qr && (
                      <div className="qr-scanned-alert">
                        📷 Mã kiện hàng: <code>{staffOp.inbound.last_scanned_qr}</code>
                      </div>
                    )}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="op-actions-row">
                  {!isRunning ? (
                    <button
                      type="button"
                      className="btn-primary-action btn-inbound"
                      onClick={handleStartInbound}
                      disabled={loading || sysMode.is_auto_running}
                    >
                      📥 BẮT ĐẦU THÊM HÀNG (LIÊN TỤC)
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn-danger-action"
                      onClick={handleStopInbound}
                      disabled={loading}
                    >
                      🏁 KẾT THÚC THÊM HÀNG
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Live Message Log */}
            <div className="staff-log-card">
              <div className="log-header">
                <span>📡 Trạng thái Hệ thống:</span>
                <span className="log-time">{new Date().toLocaleTimeString("vi-VN")}</span>
              </div>
              <div className="log-message-box">
                {staffOp.message || "Hệ thống nhân viên sẵn sàng."}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
