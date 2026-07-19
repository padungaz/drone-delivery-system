import { useEffect, useState } from "react";
import {
  createAddress,
  deleteAddress,
  getAddresses,
  updateAddress,
} from "../services/api";
import type { CustomerAddress } from "../types/customer";
import { MapPicker } from "../components/MapPicker";

const PHONE_KEY = "dronego_phone";
const NAME_KEY = "dronego_name";
const CID_KEY = "dronego_customer_id";

type Tab = "RECEIVE" | "SEND";

interface AddressForm {
  address_name: string;
  address_text: string;
  lat: string;
  lon: string;
}

const EMPTY_FORM: AddressForm = {
  address_name: "",
  address_text: "",
  lat: "",
  lon: "",
};

export function AddressManagerPage() {
  const [phone, setPhone] = useState(localStorage.getItem(PHONE_KEY) ?? "");
  const [name, setName] = useState(localStorage.getItem(NAME_KEY) ?? "");
  const [customerId, setCustomerId] = useState<number | null>(
    localStorage.getItem(CID_KEY) ? Number(localStorage.getItem(CID_KEY)) : null,
  );

  const [tab, setTab] = useState<Tab>("RECEIVE");
  const [addresses, setAddresses] = useState<CustomerAddress[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<AddressForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [modalError, setModalError] = useState("");
  const [useMap, setUseMap] = useState(false);

  const fetchAddresses = async (cid: number, t: Tab) => {
    setLoading(true);
    try {
      const data = await getAddresses(cid, t);
      setAddresses(data);
    } catch {
      setError("Không thể tải địa chỉ");
    } finally {
      setLoading(false);
    }
  };

  // When customerId changes (after phone lookup), reload
  useEffect(() => {
    if (customerId) {
      fetchAddresses(customerId, tab);
    }
  }, [customerId, tab]);

  const handlePhoneLookup = async () => {
    if (!phone || !name) return;
    setError("");
    try {
      // Create delivery with dummy coords just to get/create customer, or use a simpler endpoint
      // Actually we use createAddress which needs customer_id...
      // Workaround: The backend auto-creates customer when creating delivery.
      // For address manager, we need to know the customer_id.
      // We'll call GET /customer/address with a search — but we need customer_id.
      // Alternative: Let's call POST /customer/delivery with dummy info to get customer_id
      // or call a customer lookup endpoint.
      // For simplicity: we'll call a dedicated endpoint — or just save name/phone to local
      // storage and use the returned customer_id from a test create.
      // Best approach: after creating a delivery, the response has customer_id.
      // We store it in localStorage. If user hasn't created an order yet, prompt them.
      
      // If we already have customer_id in localStorage, use it
      const stored = localStorage.getItem(CID_KEY);
      if (stored) {
        setCustomerId(Number(stored));
        localStorage.setItem(PHONE_KEY, phone);
        localStorage.setItem(NAME_KEY, name);
        return;
      }

      setError("Tạo đơn hàng trước để sử dụng sổ địa chỉ, hoặc ID sẽ được lưu tự động sau lần đặt đơn đầu tiên.");
    } catch {
      setError("Lỗi kết nối");
    }
  };

  const handleSave = async () => {
    if (!customerId) return;
    if (!form.address_name || (!form.lat && !form.address_text)) {
      setModalError("Điền đầy đủ tên và chọn tọa độ");
      return;
    }
    setSaving(true);
    setModalError("");
    try {
      if (editId !== null) {
        await updateAddress(editId, {
          address_name: form.address_name,
          address_text: form.address_text,
          latitude: parseFloat(form.lat),
          longitude: parseFloat(form.lon),
          address_type: tab,
        });
      } else {
        const result = await createAddress({
          customer_id: customerId,
          address_type: tab,
          address_name: form.address_name,
          address_text: form.address_text,
          latitude: parseFloat(form.lat),
          longitude: parseFloat(form.lon),
        });
        // Save customer_id if not already saved
        localStorage.setItem(CID_KEY, String(result.customer_id));
      }
      setShowModal(false);
      fetchAddresses(customerId, tab);
    } catch (e: any) {
      setModalError(e.message ?? "Lỗi lưu địa chỉ");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Xóa địa chỉ này?")) return;
    try {
      await deleteAddress(id);
      if (customerId) fetchAddresses(customerId, tab);
    } catch {
      setError("Xóa thất bại");
    }
  };

  const openAdd = () => {
    setEditId(null);
    setForm(EMPTY_FORM);
    setUseMap(false);
    setModalError("");
    setShowModal(true);
  };

  const openEdit = (addr: CustomerAddress) => {
    setEditId(addr.id);
    setForm({
      address_name: addr.address_name,
      address_text: addr.address_text,
      lat: String(addr.latitude),
      lon: String(addr.longitude),
    });
    setUseMap(false);
    setModalError("");
    setShowModal(true);
  };

  const typeFiltered = addresses.filter((a) => a.address_type === tab);

  return (
    <div>
      <div className="page-header">
        <h1>📍 Sổ địa chỉ</h1>
      </div>

      {/* Customer ID section */}
      {!customerId ? (
        <div className="card">
          <p className="card-title">Xác định tài khoản</p>
          <p className="form-hint" style={{ marginBottom: "0.75rem" }}>
            Nhập thông tin để quản lý địa chỉ. Customer ID được lưu tự động sau lần đặt đơn đầu tiên.
          </p>
          <div className="form-group">
            <label className="form-label-text">Họ tên</label>
            <input
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nguyễn Văn A"
            />
          </div>
          <div className="form-group">
            <label className="form-label-text">Số điện thoại</label>
            <input
              className="form-input"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="0901234567"
            />
          </div>
          {error && <div className="alert alert-error">{error}</div>}
          <button className="btn btn-primary" onClick={handlePhoneLookup}>
            Tiếp tục →
          </button>
        </div>
      ) : (
        <>
          <div className="alert alert-info" style={{ marginBottom: "1rem" }}>
            👤 {localStorage.getItem(NAME_KEY)} · {phone}
            <button
              style={{ marginLeft: "auto", background: "transparent", border: "none", color: "var(--accent2)", cursor: "pointer", fontSize: "0.8rem" }}
              onClick={() => {
                localStorage.removeItem(CID_KEY);
                setCustomerId(null);
              }}
            >
              Đổi tài khoản
            </button>
          </div>

          {/* Tabs */}
          <div className="type-tabs" style={{ marginBottom: "1rem" }}>
            <button
              className={`type-tab ${tab === "RECEIVE" ? "active receive" : ""}`}
              onClick={() => setTab("RECEIVE")}
            >
              <span className="type-tab-icon">📦</span>
              <span className="type-tab-label">Nhận hàng</span>
              <span className="type-tab-desc">Địa chỉ nhận đồ</span>
            </button>
            <button
              className={`type-tab ${tab === "SEND" ? "active send" : ""}`}
              onClick={() => setTab("SEND")}
            >
              <span className="type-tab-icon">🚀</span>
              <span className="type-tab-label">Gửi hàng</span>
              <span className="type-tab-desc">Địa chỉ gửi đồ</span>
            </button>
          </div>

          <div className="flex-between" style={{ marginBottom: "0.75rem" }}>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              {typeFiltered.length} địa chỉ
            </p>
            <button className="btn btn-secondary btn-sm" onClick={openAdd}>
              + Thêm địa chỉ
            </button>
          </div>

          {loading ? (
            <div className="empty-state">
              <div className="spinner" style={{ margin: "0 auto", borderTopColor: "var(--accent)" }} />
            </div>
          ) : typeFiltered.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">{tab === "RECEIVE" ? "📦" : "🚀"}</div>
              <p>Chưa có địa chỉ {tab === "RECEIVE" ? "nhận" : "gửi"} nào</p>
            </div>
          ) : (
            typeFiltered.map((addr) => (
              <div key={addr.id} className="address-card">
                <div className={`address-type-icon ${tab.toLowerCase()}`}>
                  {tab === "RECEIVE" ? "📦" : "🚀"}
                </div>
                <div className="address-content">
                  <div className="address-name-text">{addr.address_name}</div>
                  <div className="address-text-text">{addr.address_text}</div>
                  <div className="address-coords-text">
                    {addr.latitude.toFixed(6)}, {addr.longitude.toFixed(6)}
                  </div>
                </div>
                <div className="address-actions">
                  <button className="btn btn-secondary btn-sm" onClick={() => openEdit(addr)}>
                    ✏️
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={() => handleDelete(addr.id)}>
                    🗑️
                  </button>
                </div>
              </div>
            ))
          )}
        </>
      )}

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">{editId ? "Sửa địa chỉ" : "Thêm địa chỉ"}</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>

            <div className="form-group">
              <label className="form-label-text">Tên địa chỉ</label>
              <input
                className="form-input"
                placeholder='VD: "Nhà", "Công ty"'
                value={form.address_name}
                onChange={(e) => setForm({ ...form, address_name: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label-text">Địa chỉ văn bản</label>
              <input
                className="form-input"
                placeholder="123 Đường ABC, TP Đà Nẵng"
                value={form.address_text}
                onChange={(e) => setForm({ ...form, address_text: e.target.value })}
              />
            </div>

            <div className="sep">hoặc chọn trên bản đồ</div>

            <button
              className="btn btn-secondary btn-sm"
              style={{ marginBottom: "0.75rem" }}
              onClick={() => setUseMap(!useMap)}
            >
              {useMap ? "Ẩn bản đồ" : "🗺️ Mở bản đồ"}
            </button>

            {useMap && (
              <MapPicker
                initialLat={parseFloat(form.lat) || undefined}
                initialLon={parseFloat(form.lon) || undefined}
                onSelect={(pos) => setForm({ ...form, lat: String(pos.lat), lon: String(pos.lon) })}
              />
            )}

            <div className="form-row-2" style={{ marginTop: "0.75rem" }}>
              <div className="form-group">
                <label className="form-label-text">Latitude</label>
                <input
                  className="form-input"
                  type="number"
                  step="0.000001"
                  value={form.lat}
                  onChange={(e) => setForm({ ...form, lat: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label-text">Longitude</label>
                <input
                  className="form-input"
                  type="number"
                  step="0.000001"
                  value={form.lon}
                  onChange={(e) => setForm({ ...form, lon: e.target.value })}
                />
              </div>
            </div>

            {modalError && <div className="alert alert-error">{modalError}</div>}

            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
              <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => setShowModal(false)}>
                Hủy
              </button>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={handleSave} disabled={saving}>
                {saving ? "Đang lưu…" : "💾 Lưu"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
