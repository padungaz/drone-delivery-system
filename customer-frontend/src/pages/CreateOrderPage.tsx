import { useEffect, useState } from "react";
import { createDelivery, getWarehouse } from "../services/api";
import type { DeliveryType, LatLon, WarehouseInfo } from "../types/customer";
import { MapPicker } from "../components/MapPicker";

interface Props {
  deliveryType: DeliveryType;
  onBack: () => void;
  onSuccess: () => void;
}

type Step = "info" | "address" | "confirm" | "done";

const TYPE_CONFIG = {
  RECEIVE_FROM_WAREHOUSE: {
    title: "📦 Nhận đồ từ kho",
    addressLabel: "Địa chỉ nhận",
    addressDesc: "Nhập địa chỉ bạn muốn nhận hàng",
    icon: "📦",
  },
  SEND_TO_WAREHOUSE: {
    title: "🚀 Gửi đồ tới kho",
    addressLabel: "Địa chỉ lấy hàng",
    addressDesc: "Nhập địa chỉ nơi drone đến lấy hàng",
    icon: "🚀",
  },
};

const PHONE_KEY = "dronego_phone";
const NAME_KEY = "dronego_name";

export function CreateOrderPage({ deliveryType, onBack, onSuccess }: Props) {
  const config = TYPE_CONFIG[deliveryType];
  const [step, setStep] = useState<Step>("info");
  const [warehouse, setWarehouse] = useState<WarehouseInfo | null>(null);
  const [warehouseError, setWarehouseError] = useState("");

  // Customer info
  const [name, setName] = useState(localStorage.getItem(NAME_KEY) ?? "");
  const [phone, setPhone] = useState(localStorage.getItem(PHONE_KEY) ?? "");

  // Customer address
  const [address, setAddress] = useState("");
  const [coords, setCoords] = useState<LatLon | null>(null);

  // Note
  const [note, setNote] = useState("");

  // Submission
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [orderId, setOrderId] = useState<number | null>(null);

  // Load warehouse
  useEffect(() => {
    getWarehouse()
      .then(setWarehouse)
      .catch(() => setWarehouseError("Không thể tải thông tin kho"));
  }, []);

  // ── Step validation ──

  const canGoAddress = name.trim().length >= 2 && phone.trim().length >= 6;
  const canGoConfirm = coords !== null;

  const handleInfoNext = () => {
    localStorage.setItem(NAME_KEY, name);
    localStorage.setItem(PHONE_KEY, phone);
    setStep("address");
  };

  const handleSubmit = async () => {
    if (!coords || !warehouse) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await createDelivery({
        customer_name: name,
        customer_phone: phone,
        delivery_type: deliveryType,
        customer_lat: coords.lat,
        customer_lon: coords.lon,
        customer_address: address,
        note,
      });
      setOrderId(res.id);
      setStep("done");
    } catch (e: any) {
      setError(e.message ?? "Tạo đơn thất bại");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Render ──

  if (step === "done" && orderId) {
    return (
      <div>
        <div className="success-hero">
          <span className="success-icon">🎉</span>
          <h1>Đặt đơn thành công!</h1>
          <p className="text2">Đơn #{orderId} đang chờ Admin duyệt.</p>
        </div>
        <div className="card">
          <p className="card-title">Bước tiếp theo</p>
          <div className="steps-list">
            <div className="step-item">
              <div className="step-num">1</div>Admin xem xét và duyệt đơn
            </div>
            <div className="step-item">
              <div className="step-num">2</div>Drone được điều phối bay
            </div>
            <div className="step-item">
              <div className="step-num">3</div>Theo dõi trạng thái tại "Đơn hàng"
            </div>
          </div>
        </div>
        <button className="btn btn-primary mt-2" onClick={onSuccess}>
          Xem đơn hàng của tôi →
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <button className="btn-back" onClick={onBack}>← Quay lại</button>
        <h1>{config.title}</h1>
      </div>

      {/* Step indicator */}
      <div style={{ display: "flex", gap: "0.4rem", marginBottom: "1.25rem" }}>
        {(["info", "address", "confirm"] as Step[]).map((s, i) => (
          <div
            key={s}
            style={{
              flex: 1,
              height: "3px",
              borderRadius: "99px",
              background:
                step === s
                  ? "var(--accent)"
                  : (["info", "address", "confirm"].indexOf(step) > i)
                  ? "var(--success)"
                  : "var(--border2)",
              transition: "background 0.3s",
            }}
          />
        ))}
      </div>

      {/* Step 1: Customer info */}
      {step === "info" && (
        <div>
          <div className="card">
            <p className="card-title">Thông tin khách hàng</p>
            <div className="form-group">
              <label className="form-label-text">Họ và tên</label>
              <input
                className="form-input"
                type="text"
                placeholder="Nguyễn Văn A"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={128}
              />
            </div>
            <div className="form-group">
              <label className="form-label-text">Số điện thoại</label>
              <input
                className="form-input"
                type="tel"
                placeholder="0901234567"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                maxLength={32}
              />
              <span className="form-hint">Dùng để tra cứu đơn hàng sau này</span>
            </div>
          </div>
          <button
            className="btn btn-primary"
            disabled={!canGoAddress}
            onClick={handleInfoNext}
          >
            Tiếp theo →
          </button>
        </div>
      )}

      {/* Step 2: Address */}
      {step === "address" && (
        <div>
          {/* Warehouse (always shown, readonly) */}
          <div className="card">
            <p className="card-title">
              {deliveryType === "RECEIVE_FROM_WAREHOUSE" ? "Điểm lấy hàng (Kho)" : "Điểm giao hàng (Kho)"}
            </p>
            {warehouseError ? (
              <div className="alert alert-error">{warehouseError}</div>
            ) : warehouse ? (
              <div className="warehouse-readonly">
                <span className="warehouse-icon">🏭</span>
                <div className="warehouse-details">
                  <div className="warehouse-name-text">{warehouse.name}</div>
                  {warehouse.address_text && (
                    <div className="warehouse-addr-text">{warehouse.address_text}</div>
                  )}
                  <div className="warehouse-addr-text" style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
                    {warehouse.latitude.toFixed(6)}, {warehouse.longitude.toFixed(6)}
                  </div>
                </div>
                <span className="warehouse-badge">🔒 Cố định</span>
              </div>
            ) : (
              <p className="muted">Đang tải...</p>
            )}
          </div>

          {/* Customer address */}
          <div className="card">
            <p className="card-title">{config.addressLabel}</p>
            <p className="form-hint" style={{ marginBottom: "0.75rem" }}>{config.addressDesc}</p>

            <div className="form-group">
              <label className="form-label-text">Địa chỉ văn bản</label>
              <input
                className="form-input"
                type="text"
                placeholder="123 Trần Phú, Đà Nẵng"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                maxLength={256}
              />
            </div>

            <MapPicker
              initialLat={warehouse?.latitude}
              initialLon={warehouse?.longitude}
              onSelect={setCoords}
              label="Hoặc chọn trên bản đồ (bắt buộc)"
            />
          </div>

          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button className="btn btn-secondary" onClick={() => setStep("info")}>
              ← Trước
            </button>
            <button
              className="btn btn-primary"
              style={{ flex: 1 }}
              disabled={!canGoConfirm}
              onClick={() => setStep("confirm")}
            >
              Xác nhận địa chỉ →
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Confirm */}
      {step === "confirm" && warehouse && coords && (
        <div>
          <div className="card">
            <p className="card-title">Xác nhận đơn hàng</p>

            {/* Summary */}
            <div
              style={{
                background: "var(--bg2)",
                borderRadius: "var(--radius-sm)",
                padding: "0.9rem 1rem",
                marginBottom: "1rem",
                display: "flex",
                flexDirection: "column",
                gap: "0.6rem",
                fontSize: "0.88rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="muted">Loại đơn</span>
                <span style={{ fontWeight: 600 }}>{config.title}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="muted">Tên</span>
                <span>{name}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="muted">SĐT</span>
                <span>{phone}</span>
              </div>
              <div style={{ height: "1px", background: "var(--border)" }} />
              {deliveryType === "RECEIVE_FROM_WAREHOUSE" ? (
                <>
                  <div>
                    <span className="muted">Lấy hàng tại (Kho):</span>
                    <p style={{ marginTop: "0.2rem" }}>
                      {warehouse.name}
                      {warehouse.address_text && ` — ${warehouse.address_text}`}
                    </p>
                  </div>
                  <div>
                    <span className="muted">Giao đến:</span>
                    <p style={{ marginTop: "0.2rem" }}>
                      {address || `${coords.lat.toFixed(6)}, ${coords.lon.toFixed(6)}`}
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <span className="muted">Lấy hàng tại:</span>
                    <p style={{ marginTop: "0.2rem" }}>
                      {address || `${coords.lat.toFixed(6)}, ${coords.lon.toFixed(6)}`}
                    </p>
                  </div>
                  <div>
                    <span className="muted">Giao đến (Kho):</span>
                    <p style={{ marginTop: "0.2rem" }}>
                      {warehouse.name}
                      {warehouse.address_text && ` — ${warehouse.address_text}`}
                    </p>
                  </div>
                </>
              )}
            </div>

            <div className="form-group">
              <label className="form-label-text">Ghi chú (tuỳ chọn)</label>
              <input
                className="form-input"
                type="text"
                placeholder="VD: Gọi trước khi đến..."
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={256}
              />
            </div>
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button className="btn btn-secondary" onClick={() => setStep("address")}>
              ← Trước
            </button>
            <button
              className="btn btn-primary"
              style={{ flex: 1 }}
              disabled={submitting}
              onClick={handleSubmit}
            >
              {submitting ? (
                <>
                  <div className="spinner" />
                  Đang gửi…
                </>
              ) : (
                "🚀 Đặt đơn ngay"
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
