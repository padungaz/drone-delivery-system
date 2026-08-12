import { useState } from "react";
import { completeDelivery, deleteDelivery, getDeliveriesByPhone } from "../services/api";
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
  const [sortBy, setSortBy] = useState<string>("NEWEST");
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  const handleDeleteOrder = async (orderId: number) => {
    if (!confirm(`⚠️ Bạn có chắc chắn muốn xóa Đơn hàng #${orderId}?`)) return;
    try {
      await deleteDelivery(orderId);
      setOrders((prev) => prev.filter((o) => o.id !== orderId));
    } catch {
      alert("Không thể xóa đơn hàng. Vui lòng thử lại!");
    }
  };

  const handleCompleteOrder = async (orderId: number) => {
    if (!confirm(`🎉 Xác nhận mô phỏng ĐÃ NHẬN HÀNG cho Đơn hàng #${orderId}? (Tự động chuyển đơn tiếp theo)`)) return;
    try {
      await completeDelivery(orderId);
      handleSearch();
    } catch {
      alert("Không thể hoàn thành đơn hàng. Vui lòng thử lại!");
    }
  };

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
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
                  Tìm thấy {orders.length} đơn hàng
                </p>
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <span className="muted" style={{ fontSize: "0.78rem" }}>Sắp xếp:</span>
                  <select
                    className="form-input"
                    style={{ padding: "0.2rem 0.5rem", fontSize: "0.78rem", width: "auto", borderRadius: "6px" }}
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                  >
                    <option value="NEWEST">⏱️ Mới nhất</option>
                    <option value="OLDEST">⏳ Cũ nhất</option>
                    <option value="STATUS">📊 Trạng thái</option>
                    <option value="ID_ASC">🔢 Mã #ID</option>
                  </select>
                </div>
              </div>

              {[...orders]
                .sort((a, b) => {
                  if (sortBy === "NEWEST") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
                  if (sortBy === "OLDEST") return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
                  if (sortBy === "STATUS") {
                    const order = ["PENDING", "APPROVED", "FLYING", "DELIVERED", "FAILED", "REJECTED"];
                    return order.indexOf(a.status) - order.indexOf(b.status);
                  }
                  if (sortBy === "ID_ASC") return a.id - b.id;
                  return 0;
                })
                .map((order) => {
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

                      {/* Status timeline */}
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

                      {/* Footer & Delete action */}
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginTop: "0.75rem",
                          paddingTop: "0.5rem",
                          borderTop: "1px solid var(--border)",
                        }}
                      >
                        <div className="order-meta">
                          <span>{new Date(order.created_at + (order.created_at.endsWith("Z") ? "" : "Z")).toLocaleString("vi-VN")}</span>
                          {order.mission_id && <span style={{ marginLeft: "0.5rem" }}>Mission #{order.mission_id}</span>}
                        </div>
                        <div style={{ display: "flex", gap: "0.4rem" }}>
                          {order.status !== "DELIVERED" && order.status !== "REJECTED" && (
                            <button
                              type="button"
                              className="btn btn-primary"
                              style={{ padding: "0.25rem 0.65rem", fontSize: "0.75rem", background: "var(--success)", borderColor: "var(--success)", color: "#fff", fontWeight: 700 }}
                              onClick={() => handleCompleteOrder(order.id)}
                              title="Mô phỏng hạ cánh giao hàng thành công"
                            >
                              🎉 Mô phỏng nhận hàng
                            </button>
                          )}
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: "0.25rem 0.65rem", fontSize: "0.75rem", color: "#ef4444", borderColor: "rgba(239,68,68,0.3)" }}
                            onClick={() => handleDeleteOrder(order.id)}
                            title="Xóa/Hủy đơn hàng"
                          >
                            🗑️ Xóa đơn
                          </button>
                        </div>
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
