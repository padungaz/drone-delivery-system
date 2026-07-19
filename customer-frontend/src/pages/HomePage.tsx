import type { DeliveryType } from "../types/customer";

interface Props {
  onSelectType: (type: DeliveryType) => void;
}

export function HomePage({ onSelectType }: Props) {
  return (
    <div>
      {/* Hero */}
      <div className="hero">
        <div className="hero-badge">
          <span>✨</span>
          <span>DRONE DELIVERY — HIỆN ĐẠI &amp; NHANH</span>
        </div>
        <h1>
          Giao hàng <span className="gradient-text">bằng drone</span>
          <br />thông minh
        </h1>
        <p className="hero-sub">
          Đặt giao hàng trong vài giây. Drone tự động bay đến tận nơi.
          Nhanh hơn, thông minh hơn.
        </p>
      </div>

      {/* Action Cards */}
      <div className="action-cards">
        <button
          className="action-card receive"
          onClick={() => onSelectType("RECEIVE_FROM_WAREHOUSE")}
        >
          <span className="action-card-icon">📦</span>
          <h2>Nhận đồ từ kho</h2>
          <p>Drone bay từ kho đến địa chỉ của bạn</p>
        </button>
        <button
          className="action-card send"
          onClick={() => onSelectType("SEND_TO_WAREHOUSE")}
        >
          <span className="action-card-icon">🚀</span>
          <h2>Gửi đồ tới kho</h2>
          <p>Drone đến lấy hàng và vận chuyển về kho</p>
        </button>
      </div>

      {/* Steps */}
      <div className="steps-section">
        <p className="steps-title">Quy trình đặt hàng</p>
        <div className="steps-list">
          {[
            { icon: "📝", text: "Nhập tên, số điện thoại và địa chỉ" },
            { icon: "📍", text: "Chọn điểm đến/đi trên bản đồ" },
            { icon: "✅", text: "Xác nhận đơn hàng" },
            { icon: "🚁", text: "Admin duyệt và drone tự động bay" },
            { icon: "🎉", text: "Giao hàng hoàn tất!" },
          ].map((s, i) => (
            <div className="step-item" key={i}>
              <div className="step-num">{i + 1}</div>
              <span>
                {s.icon} {s.text}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Info cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "0.75rem",
          marginBottom: "1rem",
        }}
      >
        {[
          { icon: "⚡", label: "Siêu nhanh", desc: "Giao trong vài phút" },
          { icon: "🎯", label: "Chính xác", desc: "Hạ cánh ArUco" },
          { icon: "🔄", label: "Realtime", desc: "Theo dõi trực tiếp" },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              padding: "1rem",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "1.5rem", marginBottom: "0.25rem" }}>{item.icon}</div>
            <div style={{ fontWeight: 600, fontSize: "0.82rem" }}>{item.label}</div>
            <div style={{ fontSize: "0.73rem", color: "var(--muted)" }}>{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
