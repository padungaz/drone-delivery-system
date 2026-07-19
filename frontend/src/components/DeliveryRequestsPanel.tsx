import { useCallback, useEffect, useState } from "react";
import {
  adminGetDeliveryRequests,
  adminUpdateDeliveryStatus,
} from "../services/api";
import type { MissionLocations } from "../types/drone";

interface DeliveryRequest {
  id: number;
  customer_name: string;
  customer_phone: string;
  delivery_type: "RECEIVE_FROM_WAREHOUSE" | "SEND_TO_WAREHOUSE";
  pickup_lat: number;
  pickup_lon: number;
  pickup_address: string;
  drop_lat: number;
  drop_lon: number;
  drop_address: string;
  status: string;
  mission_id: number | null;
  note: string;
  created_at: string;
}

interface Props {
  onLocationsSelected?: (locations: MissionLocations) => void;
  homeLat: number;
  homeLon: number;
}

const STATUS_COLORS: Record<string, string> = {
  PENDING: "#f59e0b",
  APPROVED: "#3b82f6",
  FLYING: "#8b5cf6",
  DELIVERED: "#22c55e",
  FAILED: "#ef4444",
  REJECTED: "#6b7280",
};

const DELIVERY_LABELS: Record<string, string> = {
  RECEIVE_FROM_WAREHOUSE: "📥 Nhận từ kho",
  SEND_TO_WAREHOUSE: "📤 Gửi tới kho",
};

export function DeliveryRequestsPanel({ onLocationsSelected, homeLat, homeLon }: Props) {
  const [requests, setRequests] = useState<DeliveryRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string>("");
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [message, setMessage] = useState<{ id: number; text: string; ok: boolean } | null>(null);

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminGetDeliveryRequests(filter || undefined);
      if (res.ok) {
        const data = await res.json();
        setRequests(data);
      }
    } catch {
      // silently fail, retry on next manual refresh
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchRequests();
    
    // Listen for WebSocket updates from backend
    const handleUpdate = () => fetchRequests();
    window.addEventListener("delivery_requests_update", handleUpdate);
    
    return () => {
      window.removeEventListener("delivery_requests_update", handleUpdate);
    };
  }, [fetchRequests]);

  const handleApprove = async (req: DeliveryRequest) => {
    setActionLoading(req.id);
    setMessage(null);
    try {
      const res = await adminUpdateDeliveryStatus(req.id, "APPROVED");
      if (res.ok) {
        setMessage({ id: req.id, text: "✅ Đã duyệt đơn", ok: true });
        fetchRequests();
      } else {
        const d = await res.json();
        setMessage({ id: req.id, text: d.detail ?? "Lỗi", ok: false });
      }
    } catch {
      setMessage({ id: req.id, text: "Network error", ok: false });
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (req: DeliveryRequest) => {
    if (!confirm(`Từ chối đơn #${req.id} của ${req.customer_name}?`)) return;
    setActionLoading(req.id);
    setMessage(null);
    try {
      const res = await adminUpdateDeliveryStatus(req.id, "REJECTED");
      if (res.ok) {
        setMessage({ id: req.id, text: "❌ Đã từ chối", ok: true });
        fetchRequests();
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleSelectAndStart = async (req: DeliveryRequest) => {
    if (!confirm(`Xác nhận nạp lộ trình của đơn hàng #${req.id} vào danh sách nhận/gửi để chuẩn bị bay?`)) return;
    const locations: MissionLocations = {
      home_lat: homeLat,
      home_lon: homeLon,
      pickup_lat: req.pickup_lat,
      pickup_lon: req.pickup_lon,
      drop_lat: req.drop_lat,
      drop_lon: req.drop_lon,
    };
    if (onLocationsSelected) {
      onLocationsSelected(locations);
    }
    // Update status to FLYING
    await adminUpdateDeliveryStatus(req.id, "FLYING");
    fetchRequests();
    setMessage({ id: req.id, text: "🚁 Đã tải địa chỉ vào form mission", ok: true });
  };

  const pendingCount = requests.filter((r) => r.status === "PENDING").length;

  return (
    <section className="panel delivery-requests-panel">
      <div className="panel-header-row">
        <h2>
          Đơn hàng
          {pendingCount > 0 && (
            <span className="pending-badge">{pendingCount} chờ duyệt</span>
          )}
        </h2>
        <div className="panel-header-actions">
          <select
            className="filter-select"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="">Tất cả</option>
            <option value="PENDING">Chờ duyệt</option>
            <option value="APPROVED">Đã duyệt</option>
            <option value="FLYING">Đang bay</option>
            <option value="DELIVERED">Hoàn thành</option>
            <option value="FAILED">Thất bại</option>
            <option value="REJECTED">Từ chối</option>
          </select>
          <button
            className="btn-icon"
            onClick={fetchRequests}
            disabled={loading}
            title="Làm mới"
          >
            {loading ? "⟳" : "↻"}
          </button>
        </div>
      </div>

      {requests.length === 0 ? (
        <p className="muted" style={{ textAlign: "center", padding: "2rem" }}>
          {loading ? "Đang tải..." : "Không có đơn hàng"}
        </p>
      ) : (
        <div className="delivery-list">
          {requests.map((req) => (
            <div key={req.id} className="delivery-card">
              <div className="delivery-card-header">
                <div className="delivery-id-type">
                  <span className="delivery-id">#{req.id}</span>
                  <span className="delivery-type-label">
                    {DELIVERY_LABELS[req.delivery_type] ?? req.delivery_type}
                  </span>
                </div>
                <span
                  className="delivery-status-badge"
                  style={{ background: `${STATUS_COLORS[req.status]}22`, color: STATUS_COLORS[req.status], border: `1px solid ${STATUS_COLORS[req.status]}` }}
                >
                  {req.status}
                </span>
              </div>

              <div className="delivery-customer">
                <span>👤 {req.customer_name}</span>
                <span className="muted">📞 {req.customer_phone}</span>
              </div>

              <div className="delivery-route">
                <div className="route-row">
                  <span className="route-label pickup">PICKUP</span>
                  <span className="route-addr">
                    {req.pickup_address || `${req.pickup_lat.toFixed(6)}, ${req.pickup_lon.toFixed(6)}`}
                  </span>
                </div>
                <div className="route-arrow">↓</div>
                <div className="route-row">
                  <span className="route-label drop">DROP</span>
                  <span className="route-addr">
                    {req.drop_address || `${req.drop_lat.toFixed(6)}, ${req.drop_lon.toFixed(6)}`}
                  </span>
                </div>
              </div>

              {req.note && <p className="delivery-note">📝 {req.note}</p>}

              <div className="delivery-meta muted">
                {new Date(req.created_at + (req.created_at.endsWith("Z") ? "" : "Z")).toLocaleString("vi-VN")}
              </div>

              {message?.id === req.id && (
                <p className={`action-message ${message.ok ? "success" : "error"}`}>
                  {message.text}
                </p>
              )}

              <div className="delivery-actions">
                {req.status === "PENDING" && (
                  <>
                    <button
                      className="btn btn-approve"
                      disabled={actionLoading === req.id}
                      onClick={() => handleApprove(req)}
                    >
                      {actionLoading === req.id ? "…" : "✓ Duyệt"}
                    </button>
                    <button
                      className="btn btn-reject"
                      disabled={actionLoading === req.id}
                      onClick={() => handleReject(req)}
                    >
                      ✗ Từ chối
                    </button>
                  </>
                )}
                {req.status === "APPROVED" && (
                  <button
                    className="btn btn-start"
                    disabled={actionLoading === req.id}
                    onClick={() => handleSelectAndStart(req)}
                    title="Tải địa chỉ vào form mission và bắt đầu bay"
                  >
                    🚁 Chọn & START
                  </button>
                )}
                {req.status === "FLYING" && req.mission_id && (
                  <span className="muted">Mission #{req.mission_id}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
