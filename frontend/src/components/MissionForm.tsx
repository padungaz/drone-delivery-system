import { useEffect, useState } from "react";
import type { MissionLocations } from "../types/drone";

interface Props {
  onChange: (locations: MissionLocations) => void;
  initialLocations?: MissionLocations;
}

const DEFAULT_LOCATIONS: MissionLocations = {
  home_lat: 0,
  home_lon: 0,
  pickup_lat: 0,
  pickup_lon: 0,
  drop_lat: 0,
  drop_lon: 0,
};

export function MissionForm({ onChange, initialLocations }: Props) {
  const [locations, setLocations] = useState<MissionLocations>(
    initialLocations ?? DEFAULT_LOCATIONS,
  );
  const [mode, setMode] = useState<"manual" | "auto">("auto");

  // When parent passes new locations (from DeliveryRequestsPanel), sync local form state
  useEffect(() => {
    if (initialLocations) {
      setLocations(initialLocations);
    }
  }, [initialLocations]);

  const update = (field: keyof MissionLocations, value: string) => {
    const next = { ...locations, [field]: parseFloat(value) || 0 };
    setLocations(next);
    onChange(next);
  };

  return (
    <section className="panel mission-form">
      <div className="panel-header-row">
        <h2>Mission Locations</h2>
        <div className="mode-toggle">
          <button
            className={`mode-btn ${mode === "auto" ? "active" : ""}`}
            onClick={() => setMode("auto")}
            title="Dùng địa chỉ từ đơn hàng"
          >
            📋 Từ đơn hàng
          </button>
          <button
            className={`mode-btn ${mode === "manual" ? "active" : ""}`}
            onClick={() => setMode("manual")}
            title="Nhập tay lat/lon"
          >
            ✏️ Thủ công
          </button>
        </div>
      </div>

      {mode === "auto" ? (
        <div className="auto-mode-hint">
          <div className="hint-box">
            <span className="hint-icon">ℹ️</span>
            <div>
              <strong>Chế độ từ đơn hàng</strong>
              <p className="muted">
                Duyệt đơn hàng ở panel bên dưới → Nhấn{" "}
                <strong>🚁 Chọn tọa độ</strong> để tự động điền vào đây.
              </p>
            </div>
          </div>
          {/* Show current loaded coordinates (readonly) */}
          <div className="coords-preview">
            <CoordRow label="Home" lat={locations.home_lat} lon={locations.home_lon} />
            <CoordRow label="Pickup" lat={locations.pickup_lat} lon={locations.pickup_lon} />
            <CoordRow label="Drop" lat={locations.drop_lat} lon={locations.drop_lon} />
          </div>
        </div>
      ) : (
        <div className="form-grid">
          {/* Mission Type Detector Helper Banner */}
          <div style={{ gridColumn: "1 / -1", background: "rgba(56, 189, 248, 0.1)", border: "1px solid rgba(56, 189, 248, 0.3)", padding: "8px 12px", borderRadius: "6px", fontSize: "0.88rem" }}>
            💡 <strong>Quy ước Phân biệt Đơn hàng khi nhập thủ công:</strong>
            <ul style={{ margin: "4px 0 0 18px", padding: 0, color: "var(--text-secondary, #94a3b8)" }}>
              <li><strong>📦 Kho GIAO HÀNG đi (Kho → Khách)</strong>: <code>Pickup</code> = Tọa độ Kho (Home), <code>Drop</code> = Tọa độ Khách.</li>
              <li><strong>📥 Kho NHẬN HÀNG về (Khách → Kho)</strong>: <code>Pickup</code> = Tọa độ Khách, <code>Drop</code> = Tọa độ Kho (Home).</li>
            </ul>
          </div>

          <fieldset>
            <legend>🏠 Home (Trạm Docking / Kho)</legend>
            <label>
              Lat
              <input
                type="number"
                step="0.0000001"
                value={locations.home_lat}
                onChange={(e) => update("home_lat", e.target.value)}
              />
            </label>
            <label>
              Lon
              <input
                type="number"
                step="0.0000001"
                value={locations.home_lon}
                onChange={(e) => update("home_lon", e.target.value)}
              />
            </label>
          </fieldset>
          <fieldset>
            <legend>🛫 Pickup (Điểm Lấy Hàng)</legend>
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: "2px 0 6px" }}>
              Nơi UAV cất hàng (Nhà khách nếu khách gửi về kho; Tọa độ Kho nếu kho giao đi)
            </p>
            <label>
              Lat
              <input
                type="number"
                step="0.0000001"
                value={locations.pickup_lat}
                onChange={(e) => update("pickup_lat", e.target.value)}
              />
            </label>
            <label>
              Lon
              <input
                type="number"
                step="0.0000001"
                value={locations.pickup_lon}
                onChange={(e) => update("pickup_lon", e.target.value)}
              />
            </label>
          </fieldset>
          <fieldset>
            <legend>🛬 Drop (Điểm Hạ / Giao Hàng)</legend>
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: "2px 0 6px" }}>
              Nơi UAV đặt hàng (Nhà khách nếu kho giao đi; Tọa độ Kho nếu khách gửi về kho)
            </p>
            <label>
              Lat
              <input
                type="number"
                step="0.0000001"
                value={locations.drop_lat}
                onChange={(e) => update("drop_lat", e.target.value)}
              />
            </label>
            <label>
              Lon
              <input
                type="number"
                step="0.0000001"
                value={locations.drop_lon}
                onChange={(e) => update("drop_lon", e.target.value)}
              />
            </label>
          </fieldset>
        </div>
      )}
    </section>
  );
}

function CoordRow({ label, lat, lon }: { label: string; lat: number; lon: number }) {
  const hasCoords = lat !== 0 || lon !== 0;
  return (
    <div className="coord-row">
      <span className="coord-label">{label}</span>
      <span className={`coord-value ${!hasCoords ? "muted" : ""}`}>
        {hasCoords ? `${lat.toFixed(7)}, ${lon.toFixed(7)}` : "—"}
      </span>
    </div>
  );
}
