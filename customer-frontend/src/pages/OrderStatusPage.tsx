import { useState } from "react";
import { getDeliveriesByPhone } from "../services/api";
import type { DeliveryRequest } from "../types/customer";

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  PENDING:   { label: "Chờ duyệt",    color: "#f59e0b", icon: "⏳" },
  APPROVED:  { label: "Đã duyệt",     color: "#3b82f6", icon: "✅" },
  FLYING:    { label: "Đang bay",      color: "#8b5cf6", icon: "🚁" },
  DELIVERED: { label: "Hoàn thành",   color: "#10b981", icon: "🎉" },
  FAILED:    { label: "Thất bại",      color: "#ef4444", icon: "❌" },
  REJECTED:  { label: "Từ chối",       color: "#6b7280", icon: "🚫" },
};

const TYPE_LABELS: Record<string, string> = {
  RECEIVE_FROM_WAREHOUSE: "📦 Nhận từ kho",
  SEND_TO_WAREHOUSE:      "🚀 Gửi tới kho",
};

const STATUS_STEPS = ["PENDING", "APPROVED", "FLYING", "DELIVERED"];

const PHONE_KEY = "dronego_phone";

export function OrderStatusPage() {
  const [phone, setPhone] = useState(localStorage.getItem(PHONE_KEY) ?? "");
  const [orders, setOrders] = useState<DeliveryRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  const handleSearch = async () => {
    if (!phone.trim()) return;
    localStorage.setItem(PHONE_KEY, phone);
    setLoading(true);
    setError("");
    try {
      const data = await getDeliveriesByPhone(phone.trim());
      setOrders(data);
      setSearched(true);
    } catch {
      setError("Không thể tải đơn hàng. Kiểm tra kết nối.");
    } finally {
      setLoading(false);
    }
  };

  const getStatusStep = (status: string) => {
    const idx = STATUS_STEPS.indexOf(status);
    return idx === -1 ? -1 : idx;
  };

  return (
    <div>
      <div className="page-header">
        <h1>📋 Đơn hàng của tôi</h1>
      </div>

      {/* Search by phone */}
      <div className="card">
        <p className="card-title">Tra cứu đơn hàng</p>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            className="form-input"
            type="tel"
            placeholder="Nhập số điện thoại..."
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-secondary"
            style={{ whiteSpace: "nowrap", padding: "0 1.25rem" }}
            onClick={handleSearch}
            disabled={loading}
          >
            {loading ? <div className="spinner" style={{ borderTopColor: "var(--accent)" }} /> : "🔍 Tìm"}
          </button>
        </div>
        {error && <div className="alert alert-error mt-1">{error}</div>}
      </div>

      {/* Results */}
      {searched && (
        <>
          {orders.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📭</div>
              <p>Không tìm thấy đơn hàng nào cho số <strong>{phone}</strong></p>
            </div>
          ) : (
            <>
              <p className="muted" style={{ marginBottom: "0.75rem", fontSize: "0.82rem" }}>
                Tìm thấy {orders.length} đơn hàng
              </p>
              {orders.map((order) => {
                const s = STATUS_CONFIG[order.status] ?? { label: order.status, color: "#888", icon: "?" };
                const step = getStatusStep(order.status);
                return (
                  <div key={order.id} className="card" style={{ borderTop: `3px solid ${s.color}` }}>
                    {/* Header */}
                    <div className="flex-between" style={{ marginBottom: "0.75rem" }}>
                      <div>
                        <span style={{ fontWeight: 700, color: "var(--accent2)", fontSize: "0.9rem" }}>
                          Đơn #{order.id}
                        </span>
                        <span style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "var(--muted)" }}>
                          {TYPE_LABELS[order.delivery_type]}
                        </span>
                      </div>
                      <span
                        className="status-badge"
                        style={{
                          background: `${s.color}18`,
                          color: s.color,
                          border: `1px solid ${s.color}`,
                        }}
                      >
                        {s.icon} {s.label}
                      </span>
                    </div>

                    {/* Route */}
                    <div className="order-route">
                      <div className="route-entry">
                        <div className="route-dot pickup" />
                        <span>
                          <strong>Lấy: </strong>
                          {order.pickup_address || `${order.pickup_lat.toFixed(5)}, ${order.pickup_lon.toFixed(5)}`}
                        </span>
                      </div>
                      <div className="route-entry" style={{ marginTop: "0.35rem" }}>
                        <div className="route-dot drop" />
                        <span>
                          <strong>Giao: </strong>
                          {order.drop_address || `${order.drop_lat.toFixed(5)}, ${order.drop_lon.toFixed(5)}`}
                        </span>
                      </div>
                    </div>

                    {/* Status timeline (only for non-failed/rejected) */}
                    {step >= 0 && (
                      <div style={{ marginTop: "0.75rem" }}>
                        <div
                          style={{
                            display: "flex",
                            gap: "0",
                            justifyContent: "space-between",
                            position: "relative",
                            paddingBottom: "0.5rem",
                          }}
                        >
                          <div
                            style={{
                              position: "absolute",
                              top: "10px",
                              left: "12px",
                              right: "12px",
                              height: "2px",
                              background: "var(--border2)",
                              zIndex: 0,
                            }}
                          />
                          <div
                            style={{
                              position: "absolute",
                              top: "10px",
                              left: "12px",
                              height: "2px",
                              width: step === 0 ? "0%" : step === 1 ? "33%" : step === 2 ? "66%" : "100%",
                              background: "var(--success)",
                              zIndex: 1,
                              transition: "width 0.5s ease",
                            }}
                          />
                          {STATUS_STEPS.map((s2, i) => (
                            <div
                              key={s2}
                              style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.3rem", flex: 1, zIndex: 2 }}
                            >
                              <div
                                style={{
                                  width: "20px",
                                  height: "20px",
                                  borderRadius: "50%",
                                  background: i <= step ? "var(--success)" : "var(--border2)",
                                  border: `2px solid var(--bg)`,
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  fontSize: "0.65rem",
                                  transition: "background 0.3s",
                                }}
                              >
                                {i < step ? "✓" : ""}
                              </div>
                              <span style={{ fontSize: "0.65rem", color: i <= step ? "var(--text2)" : "var(--muted)", textAlign: "center" }}>
                                {STATUS_CONFIG[s2]?.label.split(" ")[0]}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {order.note && (
                      <p style={{ fontSize: "0.78rem", color: "var(--muted)", marginTop: "0.5rem", fontStyle: "italic" }}>
                        📝 {order.note}
                      </p>
                    )}

                    <div className="order-meta" style={{ marginTop: "0.5rem" }}>
                      <span>{new Date(order.created_at + (order.created_at.endsWith("Z") ? "" : "Z")).toLocaleString("vi-VN")}</span>
                      {order.mission_id && <span>Mission #{order.mission_id}</span>}
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </>
      )}

      {!searched && !loading && (
        <div className="empty-state">
          <div className="empty-state-icon">🔍</div>
          <p>Nhập số điện thoại để xem đơn hàng</p>
        </div>
      )}
    </div>
  );
}
