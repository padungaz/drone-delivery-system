import { useEffect, useState } from "react";
import { createDelivery, getInventorySlots, getWarehouse } from "../services/api";
import type { DeliveryType, LatLon, StorageSlot, WarehouseInfo } from "../types/customer";
import { MapPicker } from "../components/MapPicker";

interface Props {
  deliveryType: DeliveryType;
  onBack: () => void;
  onSuccess: () => void;
}

type Step = "product" | "info" | "address" | "confirm" | "done";

const TYPE_CONFIG = {
  RECEIVE_FROM_WAREHOUSE: {
    title: "📦 Nhận đồ từ kho",
    addressLabel: "Địa chỉ nhận hàng",
    addressDesc: "Nhập địa chỉ hoặc chọn vị trí trên bản đồ nơi Drone hạ cánh giao đồ",
    icon: "📦",
  },
  SEND_TO_WAREHOUSE: {
    title: "🚀 Gửi đồ tới kho",
    addressLabel: "Địa chỉ lấy hàng",
    addressDesc: "Nhập địa chỉ hoặc chọn vị trí trên bản đồ nơi Drone đến lấy đồ",
    icon: "🚀",
  },
};

const PHONE_KEY = "dronego_phone";
const NAME_KEY = "dronego_name";

export function CreateOrderPage({ deliveryType, onBack, onSuccess }: Props) {
  const config = TYPE_CONFIG[deliveryType];
  const [step, setStep] = useState<Step>("product");
  const [warehouse, setWarehouse] = useState<WarehouseInfo | null>(null);
  const [warehouseError, setWarehouseError] = useState("");

  // Storage slots for RECEIVE_FROM_WAREHOUSE
  const [slots, setSlots] = useState<StorageSlot[]>([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<StorageSlot | null>(null);

  // Item details for SEND_TO_WAREHOUSE
  const [productName, setProductName] = useState("");
  const [productCategory, setProductCategory] = useState("Tài liệu");
  const [weight, setWeight] = useState("0.5");
  const [qrCode, setQrCode] = useState("");

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

  // Load inventory slots when RECEIVE_FROM_WAREHOUSE
  useEffect(() => {
    if (deliveryType === "RECEIVE_FROM_WAREHOUSE") {
      setLoadingSlots(true);
      getInventorySlots()
        .then((data) => {
          setSlots(data);
        })
        .catch(() => {
          setError("Không thể tải sản phẩm trong kho");
        })
        .finally(() => setLoadingSlots(false));
    }
  }, [deliveryType]);

  const occupiedSlots = slots.filter(
    (s) => s.status === "OCCUPIED" && s.product_id
  );

  // ── Step validation ──
  const canGoInfoFromProduct =
    deliveryType === "RECEIVE_FROM_WAREHOUSE"
      ? selectedSlot !== null
      : productName.trim().length >= 2;

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

    // Build final note string containing product metadata
    let formattedNote = note.trim();
    if (deliveryType === "RECEIVE_FROM_WAREHOUSE" && selectedSlot) {
      const slotInfo = `Mã hàng: ${selectedSlot.product_id} (Ô kho: ${selectedSlot.slot_name})`;
      formattedNote = formattedNote ? `${slotInfo} | ${formattedNote}` : slotInfo;
    } else if (deliveryType === "SEND_TO_WAREHOUSE") {
      const itemInfo = `Sản phẩm: ${productName.trim()} | Loại: ${productCategory} | Nặng: ${weight}kg${qrCode.trim() ? ` | QR: ${qrCode.trim()}` : ""}`;
      formattedNote = formattedNote ? `${itemInfo} | ${formattedNote}` : itemInfo;
    }

    try {
      const res = await createDelivery({
        customer_name: name,
        customer_phone: phone,
        delivery_type: deliveryType,
        customer_lat: coords.lat,
        customer_lon: coords.lon,
        customer_address: address,
        note: formattedNote,
      });
      setOrderId(res.id);
      setStep("done");
    } catch (e: any) {
      setError(e.message ?? "Tạo đơn thất bại");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Render Done Step ──
  if (step === "done" && orderId) {
    return (
      <div>
        <div className="success-hero">
          <span className="success-icon">🎉</span>
          <h1>Đặt đơn thành công!</h1>
          <p className="text2">Đơn #{orderId} đã được đưa vào hàng chờ hệ thống.</p>
        </div>
        <div className="card">
          <p className="card-title">Quy trình tự động tiếp theo</p>
          <div className="steps-list">
            <div className="step-item">
              <div className="step-num">1</div>Đơn hàng được lưu vào hàng chờ xử lý
            </div>
            <div className="step-item">
              <div className="step-num">2</div>Hệ thống tự động điều phối FSM (UAV + PLC + Robot) theo thứ tự FIFO
            </div>
            <div className="step-item">
              <div className="step-num">3</div>Theo dõi trạng thái thời gian thực tại "Đơn hàng của tôi"
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
        {(["product", "info", "address", "confirm"] as Step[]).map((s, i) => (
          <div
            key={s}
            style={{
              flex: 1,
              height: "3px",
              borderRadius: "99px",
              background:
                step === s
                  ? "var(--accent)"
                  : (["product", "info", "address", "confirm"].indexOf(step) > i)
                  ? "var(--success)"
                  : "var(--border2)",
              transition: "background 0.3s",
            }}
          />
        ))}
      </div>

      {/* STEP 1: Product Selection or Product Declaration */}
      {step === "product" && (
        <div>
          {deliveryType === "RECEIVE_FROM_WAREHOUSE" ? (
            <div className="card">
              <p className="card-title">1. Chọn sản phẩm cần lấy từ kho</p>
              <p className="form-hint" style={{ marginBottom: "1rem" }}>
                Danh sách các sản phẩm đang có sẵn trong 9 ô lưu trữ thông minh tại Kho.
              </p>

              {loadingSlots ? (
                <div style={{ textAlign: "center", padding: "2rem" }}>
                  <div className="spinner" style={{ borderTopColor: "var(--accent)", margin: "0 auto" }} />
                  <p className="muted" style={{ marginTop: "0.5rem" }}>Đang kiểm tra tồn kho...</p>
                </div>
              ) : occupiedSlots.length === 0 ? (
                <div className="alert alert-error" style={{ textAlign: "center", padding: "1.5rem" }}>
                  <span style={{ fontSize: "2.2rem", display: "block", marginBottom: "0.5rem" }}>⚠️</span>
                  <strong style={{ fontSize: "1.1rem" }}>Kho hiện đang hết hàng</strong>
                  <p style={{ marginTop: "0.4rem", fontSize: "0.85rem", color: "var(--text2)" }}>
                    Hiện không có sản phẩm nào được lưu trữ trong 9 ô kho (A1-C3). Vui lòng gửi đồ vào kho hoặc quay lại sau!
                  </p>
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "0.75rem" }}>
                  {occupiedSlots.map((slot) => {
                    const isSelected = selectedSlot?.id === slot.id;
                    return (
                      <div
                        key={slot.id}
                        onClick={() => setSelectedSlot(slot)}
                        style={{
                          background: isSelected ? "rgba(59,130,246,0.18)" : "var(--surface2)",
                          border: `2px solid ${isSelected ? "var(--accent)" : "var(--border)"}`,
                          borderRadius: "var(--radius-sm)",
                          padding: "0.9rem",
                          cursor: "pointer",
                          transition: "all 0.2s",
                          position: "relative",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                          <span style={{ background: "var(--accent)", color: "#fff", fontSize: "0.75rem", fontWeight: 700, padding: "0.15rem 0.5rem", borderRadius: "4px" }}>
                            Ô {slot.slot_name}
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "var(--success)", fontWeight: 600 }}>● Sẵn sàng</span>
                        </div>
                        <div style={{ fontWeight: 700, fontSize: "1rem", color: "var(--text)", marginTop: "0.2rem" }}>
                          📦 {slot.product_id}
                        </div>
                        {slot.qr_code && (
                          <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "0.2rem" }}>
                            Mã QR: {slot.qr_code}
                          </div>
                        )}
                        {slot.sender_name && (
                          <div style={{ fontSize: "0.75rem", color: "var(--text2)", marginTop: "0.2rem" }}>
                            Người gửi: {slot.sender_name}
                          </div>
                        )}
                        {isSelected && (
                          <div style={{ position: "absolute", top: "8px", right: "8px", color: "var(--accent)", fontWeight: "bold" }}>
                            ✓
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            <div className="card">
              <p className="card-title">1. Khai báo thông tin kiện hàng gửi</p>
              <div className="form-group">
                <label className="form-label-text">Tên / Mô tả sản phẩm (*)</label>
                <input
                  className="form-input"
                  type="text"
                  placeholder="VD: Laptop Dell, Hợp đồng bảo hiểm..."
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  maxLength={128}
                />
              </div>

              <div className="form-group">
                <label className="form-label-text">Loại hàng hóa</label>
                <select
                  className="form-input"
                  value={productCategory}
                  onChange={(e) => setProductCategory(e.target.value)}
                >
                  <option value="Tài liệu">📄 Tài liệu / Giấy tờ</option>
                  <option value="Thiết bị điện tử">💻 Thiết bị điện tử</option>
                  <option value="Thực phẩm">🍎 Thực phẩm / Đồ ăn</option>
                  <option value="Thời trang">👕 Quần áo / Thời trang</option>
                  <option value="Khác">📦 Hàng hóa khác</option>
                </select>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                <div className="form-group">
                  <label className="form-label-text">Khối lượng (kg)</label>
                  <input
                    className="form-input"
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="5.0"
                    placeholder="0.5"
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label-text">Mã QR Code (nếu có)</label>
                  <input
                    className="form-input"
                    type="text"
                    placeholder="VD: QR-1092"
                    value={qrCode}
                    onChange={(e) => setQrCode(e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          <button
            className="btn btn-primary mt-1"
            disabled={!canGoInfoFromProduct}
            onClick={() => setStep("info")}
          >
            Tiếp theo (Thông tin người {deliveryType === "RECEIVE_FROM_WAREHOUSE" ? "nhận" : "gửi"}) →
          </button>
        </div>
      )}

      {/* STEP 2: Customer Info */}
      {step === "info" && (
        <div>
          <div className="card">
            <p className="card-title">
              2. Thông tin người {deliveryType === "RECEIVE_FROM_WAREHOUSE" ? "nhận" : "gửi"}
            </p>
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
              <span className="form-hint">Dùng để tra cứu trạng thái đơn hàng sau này</span>
            </div>
          </div>
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button className="btn btn-secondary" onClick={() => setStep("product")}>
              ← Trước
            </button>
            <button
              className="btn btn-primary"
              style={{ flex: 1 }}
              disabled={!canGoAddress}
              onClick={handleInfoNext}
            >
              Tiếp theo (Địa chỉ) →
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: Address */}
      {step === "address" && (
        <div>
          {/* Warehouse location (readonly) */}
          <div className="card">
            <p className="card-title">
              {deliveryType === "RECEIVE_FROM_WAREHOUSE" ? "Điểm lấy hàng (Trạm Kho)" : "Điểm giao hàng (Trạm Kho)"}
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
                <span className="warehouse-badge">🔒 Trạm Kho cố định</span>
              </div>
            ) : (
              <p className="muted">Đang tải...</p>
            )}
          </div>

          {/* Customer address */}
          <div className="card">
            <p className="card-title">3. {config.addressLabel}</p>
            <p className="form-hint" style={{ marginBottom: "0.75rem" }}>{config.addressDesc}</p>

            <div className="form-group">
              <label className="form-label-text">Địa chỉ dạng văn bản</label>
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
              label="Chọn tọa độ hạ cánh UAV trên bản đồ (Bắt buộc)"
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

      {/* STEP 4: Confirm */}
      {step === "confirm" && warehouse && coords && (
        <div>
          <div className="card">
            <p className="card-title">4. Xác nhận chi tiết đơn hàng</p>

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
              {deliveryType === "RECEIVE_FROM_WAREHOUSE" && selectedSlot && (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span className="muted">Sản phẩm lấy</span>
                    <span style={{ fontWeight: 700, color: "var(--accent2)" }}>
                      {selectedSlot.product_id} (Ô {selectedSlot.slot_name})
                    </span>
                  </div>
                </>
              )}
              {deliveryType === "SEND_TO_WAREHOUSE" && (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span className="muted">Tên hàng gửi</span>
                    <span style={{ fontWeight: 700 }}>{productName}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span className="muted">Phân loại & Cân nặng</span>
                    <span>{productCategory} ({weight} kg)</span>
                  </div>
                </>
              )}
              <div style={{ height: "1px", background: "var(--border)" }} />
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="muted">Họ tên</span>
                <span>{name}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="muted">Số điện thoại</span>
                <span>{phone}</span>
              </div>
              <div style={{ height: "1px", background: "var(--border)" }} />
              {deliveryType === "RECEIVE_FROM_WAREHOUSE" ? (
                <>
                  <div>
                    <span className="muted">Lấy từ Kho:</span>
                    <p style={{ marginTop: "0.2rem" }}>
                      {warehouse.name} ({warehouse.latitude.toFixed(5)}, {warehouse.longitude.toFixed(5)})
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
                    <span className="muted">Drone đến lấy tại:</span>
                    <p style={{ marginTop: "0.2rem" }}>
                      {address || `${coords.lat.toFixed(6)}, ${coords.lon.toFixed(6)}`}
                    </p>
                  </div>
                  <div>
                    <span className="muted">Vận chuyển về Kho:</span>
                    <p style={{ marginTop: "0.2rem" }}>
                      {warehouse.name} ({warehouse.latitude.toFixed(5)}, {warehouse.longitude.toFixed(5)})
                    </p>
                  </div>
                </>
              )}
            </div>

            <div className="form-group">
              <label className="form-label-text">Ghi chú bổ sung (tuỳ chọn)</label>
              <input
                className="form-input"
                type="text"
                placeholder="VD: Gọi trước khi hạ cánh..."
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
                  Đang tạo đơn…
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
