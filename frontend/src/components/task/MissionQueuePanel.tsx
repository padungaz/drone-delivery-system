import { useState, useEffect, useCallback } from "react";
import { getMissionQueue, cancelMission, createMission, resetSampleOrders } from "../../services/api";
import { UavFleetControlWidget } from "./UavFleetControlWidget";

export interface MissionItem {
  id: number;
  order_id?: number | null;
  mission_type: "DRONE_PICKUP" | "DRONE_DELIVERY";
  drone_id: string;
  product_id: string;
  target_slot?: string | null;
  status: "WAITING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  current_phase: string;
  priority: number;
  error_reason?: string | null;
  step_details: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface MissionQueueData {
  active_mission: MissionItem | null;
  waiting_queue: MissionItem[];
  total_waiting: number;
  total_completed: number;
  total_failed: number;
}

export function MissionQueuePanel() {
  const [queueData, setQueueData] = useState<MissionQueueData>({
    active_mission: null,
    waiting_queue: [],
    total_waiting: 0,
    total_completed: 0,
    total_failed: 0,
  });
  const [loading, setLoading] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ text: string; isError: boolean } | null>(null);

  // Form for enqueuing new mission
  const [newType, setNewType] = useState<"DRONE_PICKUP" | "DRONE_DELIVERY">("DRONE_PICKUP");
  const [newProductId, setNewProductId] = useState("PRD-1005");
  const [newSlot, setNewSlot] = useState("B2");
  const [newPriority, setNewPriority] = useState(0);

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getMissionQueue();
      if (res.ok) {
        const data: MissionQueueData = await res.json();
        setQueueData(data);
      }
    } catch {
      // Ignore polling errors
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
    const interval = setInterval(fetchQueue, 8000);

    const handleQueueUpdate = () => fetchQueue();
    window.addEventListener("mission_queue_update", handleQueueUpdate);
    window.addEventListener("mission_started", handleQueueUpdate);
    window.addEventListener("mission_completed", handleQueueUpdate);
    window.addEventListener("mission_failed", handleQueueUpdate);

    return () => {
      clearInterval(interval);
      window.removeEventListener("mission_queue_update", handleQueueUpdate);
      window.removeEventListener("mission_started", handleQueueUpdate);
      window.removeEventListener("mission_completed", handleQueueUpdate);
      window.removeEventListener("mission_failed", handleQueueUpdate);
    };
  }, [fetchQueue]);

  const handleCancelMission = async (id: number) => {
    if (!confirm(`Xác nhận HỦY đơn hàng Mission #${id} khỏi hàng chờ?`)) return;
    setActionLoadingId(id);
    setMsg(null);
    try {
      const res = await cancelMission(id);
      if (res.ok) {
        setMsg({ text: `✅ Đã hủy Nhiệm vụ #${id} thành công!`, isError: false });
        fetchQueue();
      } else {
        const err = await res.json();
        setMsg({ text: `❌ Lỗi hủy đơn: ${err.detail || "Thất bại"}`, isError: true });
      }
    } catch {
      setMsg({ text: "❌ Lỗi kết nối server", isError: true });
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleCreateMission = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    try {
      const res = await createMission({
        mission_type: newType,
        product_id: newProductId,
        target_slot: newSlot,
        priority: newPriority,
      });
      if (res.ok) {
        setMsg({ text: `🚀 Đã thêm Nhiệm vụ mới (${newType} ${newProductId}) vào Hàng chờ FIFO!`, isError: false });
        setNewProductId(`PRD-${Math.floor(1000 + Math.random() * 9000)}`);
        fetchQueue();
      } else {
        const err = await res.json();
        setMsg({ text: `❌ Lỗi tạo nhiệm vụ: ${err.detail || "Thất bại"}`, isError: true });
      }
    } catch {
      setMsg({ text: "❌ Lỗi kết nối server", isError: true });
    }
  };

  const active = queueData.active_mission;
  const queue = queueData.waiting_queue;

  return (
    <div className="mission-queue-panel-container">
      {/* Top Header & Summary Statistics */}
      <div className="panel-header-row flex-between">
        <div className="title-box">
          <h2>📋 MISSION QUEUE MANAGER (FIFO)</h2>
          <span className="subtitle">Hệ thống Quản lý Hàng đợi & Thực thi Tự động Liên hoàn</span>
        </div>
        <div className="stats-badges-group">
          <button
            type="button"
            className="btn btn-sm btn-outline"
            onClick={async () => {
              if (!confirm("⚠️ Xác nhận XÓA SẠCH toàn bộ lịch sử và TẠO NHANH 10 ĐƠN HÀNG MỚI trong hàng chờ FIFO?")) return;
              setLoading(true);
              try {
                const res = await resetSampleOrders();
                if (res.ok) {
                  setMsg({ text: "✅ Đã tạo thành công 10 đơn hàng mới trong hàng chờ FIFO!", isError: false });
                  fetchQueue();
                } else {
                  setMsg({ text: "❌ Lỗi khi khởi tạo đơn hàng", isError: true });
                }
              } catch {
                setMsg({ text: "❌ Lỗi kết nối", isError: true });
              } finally {
                setLoading(false);
              }
            }}
            disabled={loading}
            title="Xóa toàn bộ đơn cũ và tạo nhanh 10 đơn hàng mẫu vào hàng chờ FIFO"
            style={{ fontSize: "0.75rem", padding: "0.25rem 0.6rem", borderColor: "#00F0FF", color: "#00F0FF" }}
          >
            ⚡ Tạo 10 Đơn Mẫu
          </button>
          <span className="stat-pill stat-running">
            <span className="dot online"></span> Đang chạy: <strong>{active ? 1 : 0}</strong>
          </span>
          <span className="stat-pill stat-waiting">
            <span className="dot waiting"></span> Chờ FIFO: <strong>{queueData.total_waiting}</strong>
          </span>
          <span className="stat-pill stat-completed">
            <span className="dot completed"></span> Hoàn thành: <strong>{queueData.total_completed}</strong>
          </span>
          <button
            type="button"
            className="btn-icon"
            onClick={fetchQueue}
            disabled={loading}
            title="Làm mới Hàng chờ"
          >
            {loading ? "⟳" : "↻"}
          </button>
        </div>
      </div>

      {msg && (
        <div className={`status-msg-banner ${msg.isError ? "error" : "success"}`}>
          {msg.text}
        </div>
      )}

      {/* UAV Fleet Controller & Simulation Trigger Widget */}
      <UavFleetControlWidget
        activeMissionDroneId={active?.drone_id}
        activeMissionType={active?.mission_type}
        onRefreshQueue={fetchQueue}
      />

      {/* Main Grid Layout */}
      <div className="queue-main-grid">
        {/* Left Column: Active Mission + Add Form */}
        <div className="queue-column-left">
          {/* Current Running Mission Card */}
          <div className="hmi-card active-mission-card">
            <div className="card-header flex-between">
              <h3>⚡ CURRENT RUNNING MISSION</h3>
              {active && (
                <span className="status-badge running-glow">
                  ● RUNNING
                </span>
              )}
            </div>

            <div className="card-body">
              {active ? (
                <div className="active-mission-details">
                  <div className="active-hero-header">
                    <div className="mission-id-tag">#{active.id}</div>
                    <div className="mission-type-pill">
                      {active.mission_type === "DRONE_PICKUP" ? "📥 NHẬP KHO (PICKUP)" : "📤 XUẤT KHO (DELIVERY)"}
                    </div>
                  </div>

                  <div className="active-info-grid">
                    <div className="info-cell">
                      <span className="lbl">Mã Sản Phẩm:</span>
                      <strong className="val text-cyan">{active.product_id}</strong>
                    </div>
                    <div className="info-cell">
                      <span className="lbl">Ô Kho Target:</span>
                      <strong className="val text-amber">{active.target_slot || "TỰ ĐỘNG"}</strong>
                    </div>
                    <div className="info-cell">
                      <span className="lbl">Drone ID:</span>
                      <strong className="val">{active.drone_id}</strong>
                    </div>
                    <div className="info-cell">
                      <span className="lbl">Ưu tiên (Priority):</span>
                      <strong className="val">{active.priority}</strong>
                    </div>
                  </div>

                  <div className="active-step-details-box">
                    <span className="step-title font-mono">GIAI ĐOẠN HIỆN TẠI ({active.current_phase}):</span>
                    <p className="step-desc">{active.step_details || "Đang xử lý phần cứng Trạm Docking..."}</p>
                  </div>
                </div>
              ) : (
                <div className="empty-active-placeholder">
                  <span className="empty-icon">💤</span>
                  <h4>KHÔNG CÓ NHIỆM VỤ ĐANG CHẠY</h4>
                  <p>Hệ thống đang ở trạng thái Ready. Nhiệm vụ tiếp theo trong Hàng chờ FIFO sẽ tự động kích hoạt.</p>
                </div>
              )}
            </div>
          </div>

          {/* Quick Enqueue Form Card */}
          <div className="hmi-card enqueue-form-card">
            <div className="card-header">
              <h3>➕ THÊM NHIỆM VỤ VÀO HÀNG CHỜ (FIFO)</h3>
            </div>
            <form onSubmit={handleCreateMission} className="card-body form-layout">
              <div className="form-row-2">
                <div className="form-group">
                  <label>Loại Nhiệm vụ:</label>
                  <select
                    className="hmi-input"
                    value={newType}
                    onChange={(e) => setNewType(e.target.value as any)}
                  >
                    <option value="DRONE_PICKUP">📥 DRONE_PICKUP (Nhập kho từ Drone)</option>
                    <option value="DRONE_DELIVERY">📤 DRONE_DELIVERY (Xuất kho giao Drone)</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Mã Sản Phẩm (Product ID):</label>
                  <input
                    type="text"
                    className="hmi-input"
                    value={newProductId}
                    onChange={(e) => setNewProductId(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="form-row-2">
                <div className="form-group">
                  <label>Ô Kho Target Slot:</label>
                  <select
                    className="hmi-input"
                    value={newSlot}
                    onChange={(e) => setNewSlot(e.target.value)}
                  >
                    {["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"].map((s) => (
                      <option key={s} value={s}>Slot {s}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Mức Ưu tiên (Priority):</label>
                  <input
                    type="number"
                    className="hmi-input"
                    value={newPriority}
                    onChange={(e) => setNewPriority(Number(e.target.value))}
                    min={0}
                    max={10}
                  />
                </div>
              </div>

              <button type="submit" className="btn-hmi btn-primary btn-block">
                🚀 ĐẨY ĐƠN VÀO QUEUE (FIFO)
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Waiting Queue (FIFO) List */}
        <div className="queue-column-right">
          <div className="hmi-card waiting-queue-card">
            <div className="card-header flex-between">
              <h3>⏳ NEXT MISSIONS WAITING (FIFO QUEUE)</h3>
              <span className="queue-count-badge">{queue.length} Đơn hàng chờ</span>
            </div>

            <div className="card-body queue-table-body">
              {queue.length === 0 ? (
                <div className="empty-queue-msg">
                  <p>✨ Hàng chờ đang trống. Không có đơn hàng nào chờ thực thi.</p>
                </div>
              ) : (
                <div className="queue-list-table">
                  {queue.map((m, idx) => (
                    <div key={m.id} className="queue-table-row">
                      <div className="q-rank font-mono">#{idx + 1}</div>
                      <div className="q-info">
                        <div className="q-top">
                          <span className="q-id font-mono">Mission #{m.id}</span>
                          <span className={`q-type-badge ${m.mission_type.toLowerCase()}`}>
                            {m.mission_type}
                          </span>
                        </div>
                        <div className="q-sub muted">
                          Sản phẩm: <strong className="text-cyan">{m.product_id}</strong> · Slot: <strong>{m.target_slot || "A1"}</strong> · Drone: {m.drone_id}
                        </div>
                      </div>
                      <div className="q-meta font-mono">
                        <span className="q-time">{new Date(m.created_at).toLocaleTimeString("vi-VN")}</span>
                        <span className="q-status-waiting">WAITING</span>
                      </div>
                      <div className="q-actions">
                        <button
                          type="button"
                          className="btn-cancel-sm"
                          disabled={actionLoadingId === m.id}
                          onClick={() => handleCancelMission(m.id)}
                          title="Hủy đơn hàng này khỏi Hàng chờ"
                        >
                          {actionLoadingId === m.id ? "…" : "✖ Hủy"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
