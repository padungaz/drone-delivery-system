import { useEffect, useState } from "react";
import { adminGetWarehouse, adminUpdateWarehouse } from "../services/api";

interface WarehouseConfig {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  address_text: string;
  updated_at: string;
}

interface Props {
  onWarehouseLoaded?: (lat: number, lon: number) => void;
}

export function WarehouseConfigPanel({ onWarehouseLoaded }: Props) {
  const [config, setConfig] = useState<WarehouseConfig | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    name: "",
    latitude: "",
    longitude: "",
    address_text: "",
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const fetchWarehouse = async () => {
    try {
      const res = await adminGetWarehouse();
      if (res.ok) {
        const data: WarehouseConfig = await res.json();
        setConfig(data);
        setForm({
          name: data.name,
          latitude: String(data.latitude),
          longitude: String(data.longitude),
          address_text: data.address_text,
        });
        onWarehouseLoaded?.(data.latitude, data.longitude);
      }
    } catch {
      // silently fail
    }
  };

  useEffect(() => {
    fetchWarehouse();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const res = await adminUpdateWarehouse({
        name: form.name,
        latitude: parseFloat(form.latitude),
        longitude: parseFloat(form.longitude),
        address_text: form.address_text,
      });
      if (res.ok) {
        const data: WarehouseConfig = await res.json();
        setConfig(data);
        onWarehouseLoaded?.(data.latitude, data.longitude);
        setEditing(false);
        setMessage({ text: "✅ Đã cập nhật kho", ok: true });
      } else {
        const d = await res.json();
        setMessage({ text: d.detail ?? "Lỗi cập nhật", ok: false });
      }
    } catch {
      setMessage({ text: "Network error", ok: false });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel warehouse-config-panel">
      <div className="panel-header-row">
        <h2>🏭 Kho hàng</h2>
        {!editing && (
          <button className="btn-icon" onClick={() => setEditing(true)} title="Chỉnh sửa">
            ✏️
          </button>
        )}
      </div>

      {message && (
        <p className={`action-message ${message.ok ? "success" : "error"}`}>{message.text}</p>
      )}

      {editing ? (
        <div className="warehouse-form">
          <label className="form-label">
            Tên kho
            <input
              className="form-input"
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
          <label className="form-label">
            Địa chỉ
            <input
              className="form-input"
              type="text"
              placeholder="VD: 123 Nguyễn Văn A, Đà Nẵng"
              value={form.address_text}
              onChange={(e) => setForm({ ...form, address_text: e.target.value })}
            />
          </label>
          <div className="form-row">
            <label className="form-label">
              Latitude
              <input
                className="form-input"
                type="number"
                step="0.000001"
                value={form.latitude}
                onChange={(e) => setForm({ ...form, latitude: e.target.value })}
              />
            </label>
            <label className="form-label">
              Longitude
              <input
                className="form-input"
                type="number"
                step="0.000001"
                value={form.longitude}
                onChange={(e) => setForm({ ...form, longitude: e.target.value })}
              />
            </label>
          </div>
          <div className="form-actions">
            <button className="btn btn-approve" onClick={handleSave} disabled={loading}>
              {loading ? "Đang lưu…" : "💾 Lưu"}
            </button>
            <button
              className="btn btn-stop"
              onClick={() => { setEditing(false); setMessage(null); }}
              disabled={loading}
            >
              Hủy
            </button>
          </div>
        </div>
      ) : config ? (
        <div className="warehouse-info">
          <div className="warehouse-name">{config.name}</div>
          {config.address_text && (
            <div className="warehouse-address muted">{config.address_text}</div>
          )}
          <div className="warehouse-coords muted">
            📍 {config.latitude.toFixed(6)}, {config.longitude.toFixed(6)}
          </div>
          <div className="warehouse-updated muted" style={{ fontSize: "0.75rem", marginTop: "0.25rem" }}>
            Cập nhật: {new Date(config.updated_at + (config.updated_at.endsWith("Z") ? "" : "Z")).toLocaleString("vi-VN")}
          </div>
        </div>
      ) : (
        <p className="muted">Đang tải...</p>
      )}
    </section>
  );
}
