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

  // When parent passes new locations (from DeliveryRequestsPanel), sync them
  useEffect(() => {
    if (initialLocations) {
      setLocations(initialLocations);
      onChange(initialLocations);
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
                <strong>🚁 Chọn &amp; START</strong> để tự động điền tọa độ vào đây.
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
          <fieldset>
            <legend>Home</legend>
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
            <legend>Pickup</legend>
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
            <legend>Drop</legend>
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
