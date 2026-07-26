import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { MissionLocations, Telemetry } from "../types/drone";

interface Props {
  telemetry: Telemetry | null;
  locations: MissionLocations;
  droneOnline: boolean;
}

// Custom DivIcons for map markers
const createCustomIcon = (emoji: string, color: string, label: string, rotation: number = 0) => {
  return L.divIcon({
    className: "custom-map-marker",
    html: `
      <div style="
        background-color: ${color};
        width: 38px;
        height: 38px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
        border: 2px solid #ffffff;
        transform: rotate(${rotation}deg);
        transition: transform 0.3s ease;
      ">
        ${emoji}
      </div>
      <div style="
        position: absolute;
        bottom: -18px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(15, 23, 42, 0.85);
        color: #f8fafc;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 600;
        white-space: nowrap;
        border: 1px solid rgba(255,255,255,0.2);
      ">
        ${label}
      </div>
    `,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    popupAnchor: [0, -20],
  });
};

export function MapPanel({ telemetry, locations, droneOnline }: Props) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  // Markers
  const droneMarkerRef = useRef<L.Marker | null>(null);
  const homeMarkerRef = useRef<L.Marker | null>(null);
  const pickupMarkerRef = useRef<L.Marker | null>(null);
  const dropMarkerRef = useRef<L.Marker | null>(null);

  // Polylines
  const plannedPathRef = useRef<L.Polyline | null>(null);
  const flightTrailRef = useRef<L.Polyline | null>(null);

  // Flight history trail coordinates
  const [trail, setTrail] = useState<[number, number][]>([]);
  const [followDrone, setFollowDrone] = useState(true);

  // Initial Map Setup
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Default center (Da Nang or configured home location)
    const initialLat = locations.home_lat || telemetry?.latitude || 16.0544;
    const initialLon = locations.home_lon || telemetry?.longitude || 108.2022;

    const map = L.map(mapContainerRef.current, {
      center: [initialLat, initialLon],
      zoom: 16,
      zoomControl: true,
    });

    // Dark-themed tile layer (OpenStreetMap / CartoDB Voyager)
    L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
    }).addTo(map);

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update Mission Locations (Home, Pickup, Drop Markers & Planned Path)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // 1. Home / Warehouse Marker
    if (locations.home_lat && locations.home_lon) {
      const pos: [number, number] = [locations.home_lat, locations.home_lon];
      if (!homeMarkerRef.current) {
        homeMarkerRef.current = L.marker(pos, {
          icon: createCustomIcon("🏠", "#3b82f6", "Kho hàng"),
        })
          .addTo(map)
          .bindPopup("<b>🏠 Trạm xuất phát (Kho)</b><br/>" + pos[0] + ", " + pos[1]);
      } else {
        homeMarkerRef.current.setLatLng(pos);
      }
    } else if (homeMarkerRef.current) {
      homeMarkerRef.current.remove();
      homeMarkerRef.current = null;
    }

    // 2. Pickup Marker
    if (locations.pickup_lat && locations.pickup_lon) {
      const pos: [number, number] = [locations.pickup_lat, locations.pickup_lon];
      if (!pickupMarkerRef.current) {
        pickupMarkerRef.current = L.marker(pos, {
          icon: createCustomIcon("📦", "#f59e0b", "Lấy hàng"),
        })
          .addTo(map)
          .bindPopup("<b>📦 Điểm lấy hàng (Pickup)</b><br/>" + pos[0] + ", " + pos[1]);
      } else {
        pickupMarkerRef.current.setLatLng(pos);
      }
    } else if (pickupMarkerRef.current) {
      pickupMarkerRef.current.remove();
      pickupMarkerRef.current = null;
    }

    // 3. Drop Marker
    if (locations.drop_lat && locations.drop_lon) {
      const pos: [number, number] = [locations.drop_lat, locations.drop_lon];
      if (!dropMarkerRef.current) {
        dropMarkerRef.current = L.marker(pos, {
          icon: createCustomIcon("📬", "#ef4444", "Giao hàng"),
        })
          .addTo(map)
          .bindPopup("<b>📬 Điểm giao hàng (Drop)</b><br/>" + pos[0] + ", " + pos[1]);
      } else {
        dropMarkerRef.current.setLatLng(pos);
      }
    } else if (dropMarkerRef.current) {
      dropMarkerRef.current.remove();
      dropMarkerRef.current = null;
    }

    // 4. Planned Path Line (Home -> Pickup -> Drop -> Home)
    const points: [number, number][] = [];
    if (locations.home_lat && locations.home_lon) points.push([locations.home_lat, locations.home_lon]);
    if (locations.pickup_lat && locations.pickup_lon) points.push([locations.pickup_lat, locations.pickup_lon]);
    if (locations.drop_lat && locations.drop_lon) points.push([locations.drop_lat, locations.drop_lon]);
    if (locations.home_lat && locations.home_lon && points.length > 2) {
      points.push([locations.home_lat, locations.home_lon]);
    }

    if (points.length >= 2) {
      if (!plannedPathRef.current) {
        plannedPathRef.current = L.polyline(points, {
          color: "#38bdf8",
          weight: 3,
          dashArray: "8, 8",
          opacity: 0.8,
        }).addTo(map);
      } else {
        plannedPathRef.current.setLatLngs(points);
      }
    } else if (plannedPathRef.current) {
      plannedPathRef.current.remove();
      plannedPathRef.current = null;
    }
  }, [locations]);

  // Update Drone Telemetry Marker & Flight Trail
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !telemetry || !droneOnline) return;

    const lat = telemetry.latitude;
    const lon = telemetry.longitude;

    if (!lat || !lon || (lat === 0 && lon === 0)) return;

    const dronePos: [number, number] = [lat, lon];
    const heading = telemetry.heading || 0;

    // Update or Create Drone Marker
    if (!droneMarkerRef.current) {
      droneMarkerRef.current = L.marker(dronePos, {
        icon: createCustomIcon("🛸", "#10b981", "Drone", heading),
        zIndexOffset: 1000,
      }).addTo(map);
    } else {
      droneMarkerRef.current.setLatLng(dronePos);
      droneMarkerRef.current.setIcon(createCustomIcon("🛸", "#10b981", "Drone", heading));
    }

    // Popup content
    const popupContent = `
      <div style="font-family: sans-serif; font-size: 12px; line-height: 1.5;">
        <strong style="color: #10b981;">🛸 Drone Telemetry</strong><br/>
        <b>Trạng thái:</b> ${telemetry.drone_state}<br/>
        <b>Pin:</b> ${telemetry.battery}% | <b>Vận tốc:</b> ${telemetry.ground_speed} m/s<br/>
        <b>Độ cao AGL:</b> ${telemetry.altitude_agl.toFixed(1)}m<br/>
        <b>GPS:</b> ${telemetry.gps_satellite} vệ tinh
      </div>
    `;
    droneMarkerRef.current.bindPopup(popupContent);

    // Auto-center map on drone if followDrone is enabled
    if (followDrone) {
      map.panTo(dronePos, { animate: true, duration: 0.5 });
    }

    // Append to flight history trail
    setTrail((prev) => {
      const lastPoint = prev[prev.length - 1];
      if (!lastPoint || lastPoint[0] !== lat || lastPoint[1] !== lon) {
        const updated = [...prev, dronePos];
        // Keep max 500 points for smooth performance
        return updated.length > 500 ? updated.slice(updated.length - 500) : updated;
      }
      return prev;
    });
  }, [telemetry, droneOnline, followDrone]);

  // Update Flight Trail Polyline on Map
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (trail.length >= 2) {
      if (!flightTrailRef.current) {
        flightTrailRef.current = L.polyline(trail, {
          color: "#10b981",
          weight: 4,
          opacity: 0.85,
        }).addTo(map);
      } else {
        flightTrailRef.current.setLatLngs(trail);
      }
    }
  }, [trail]);

  // Fit view bounds to contain all active markers
  const handleFitBounds = () => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const bounds = L.latLngBounds([]);
    if (locations.home_lat && locations.home_lon) bounds.extend([locations.home_lat, locations.home_lon]);
    if (locations.pickup_lat && locations.pickup_lon) bounds.extend([locations.pickup_lat, locations.pickup_lon]);
    if (locations.drop_lat && locations.drop_lon) bounds.extend([locations.drop_lat, locations.drop_lon]);
    if (telemetry?.latitude && telemetry?.longitude && telemetry.latitude !== 0) {
      bounds.extend([telemetry.latitude, telemetry.longitude]);
    }

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  };

  return (
    <div className="panel map-panel-wrapper" style={{ padding: 0, overflow: "hidden", position: "relative" }}>
      {/* Map Control Floating Bar */}
      <div className="map-toolbar">
        <div className="map-toolbar-title">
          <span>🗺️ Live Map Tracking</span>
          {droneOnline && telemetry && (
            <span className="badge online" style={{ marginLeft: "8px", fontSize: "11px" }}>
              {telemetry.drone_state}
            </span>
          )}
        </div>

        <div className="map-toolbar-actions">
          <button
            type="button"
            className={`btn-map-action ${followDrone ? "active" : ""}`}
            onClick={() => setFollowDrone(!followDrone)}
            title="Tự động cuộn bản đồ theo vị trí Drone"
          >
            🎯 {followDrone ? "Đang theo drone" : "Theo dõi drone"}
          </button>
          <button
            type="button"
            className="btn-map-action"
            onClick={handleFitBounds}
            title="Zoom hiển thị toàn bộ lộ trình"
          >
            🔍 Zoom toàn bộ
          </button>
          {trail.length > 0 && (
            <button
              type="button"
              className="btn-map-action"
              onClick={() => setTrail([])}
              title="Xóa vết đường bay cũ"
            >
              🧹 Xóa đường bay
            </button>
          )}
        </div>
      </div>

      {/* Main Leaflet Container */}
      <div ref={mapContainerRef} className="map-container-box" style={{ width: "100%", height: "550px" }} />

      {/* Floating Telemetry HUD overlay on map */}
      {droneOnline && telemetry && (
        <div className="map-hud-overlay">
          <div className="hud-item">
            <span className="hud-label">ALT</span>
            <span className="hud-value">{telemetry.altitude_agl.toFixed(1)} m</span>
          </div>
          <div className="hud-item">
            <span className="hud-label">SPEED</span>
            <span className="hud-value">{telemetry.ground_speed.toFixed(1)} m/s</span>
          </div>
          <div className="hud-item">
            <span className="hud-label">BATTERY</span>
            <span className="hud-value" style={{ color: telemetry.battery > 30 ? "#10b981" : "#ef4444" }}>
              {telemetry.battery}%
            </span>
          </div>
          <div className="hud-item">
            <span className="hud-label">GPS</span>
            <span className="hud-value">{telemetry.gps_satellite} SATS</span>
          </div>
        </div>
      )}
    </div>
  );
}
