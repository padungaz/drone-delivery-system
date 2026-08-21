import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { MissionLocations, Telemetry } from "../types/drone";

interface Props {
  telemetry: Telemetry | null;
  locations: MissionLocations;
  droneOnline: boolean;
  selectedTarget?: { lat: number; lon: number } | null;
  onSelectTarget?: (target: { lat: number; lon: number } | null) => void;
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
        transition: transform 0.2s ease;
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

export const MapPanel = React.memo(function MapPanel({
  telemetry,
  locations,
  droneOnline,
  selectedTarget,
  onSelectTarget,
}: Props) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  // Target selection callback ref for map click event
  const onSelectTargetRef = useRef(onSelectTarget);
  onSelectTargetRef.current = onSelectTarget;

  // Markers
  const droneMarkerRef = useRef<L.Marker | null>(null);
  const homeMarkerRef = useRef<L.Marker | null>(null);
  const pickupMarkerRef = useRef<L.Marker | null>(null);
  const dropMarkerRef = useRef<L.Marker | null>(null);
  const targetMarkerRef = useRef<L.Marker | null>(null);

  // Polylines
  const plannedPathRef = useRef<L.Polyline | null>(null);
  const flightTrailRef = useRef<L.Polyline | null>(null);
  const targetLineRef = useRef<L.Polyline | null>(null);
  const trailPointsRef = useRef<[number, number][]>([]);
  const lastHeadingRef = useRef<number>(-999);
  const lastPanTimeRef = useRef<number>(0);

  // Flight history trail coordinates
  const [trail, setTrail] = useState<[number, number][]>([]);
  const [followDrone, setFollowDrone] = useState(true);

  // Initial Map Setup
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Default center (Da Nang or configured home location)
    const initialLat = locations.home_lat || telemetry?.latitude || 16.0544;
    const initialLon = locations.home_lon || telemetry?.longitude || 108.2022;
    // Dark-themed tile layer (OpenStreetMap / CartoDB Voyager / Esri Satellite)
    const map = L.map(mapContainerRef.current, {
      center: [initialLat, initialLon],
      zoom: 17,
      maxZoom: 22,
      zoomControl: true,
    });

    const streetLayer = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
      maxNativeZoom: 19,
      maxZoom: 22,
    });

    const satelliteLayer = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        attribution: "Tiles &copy; Esri &mdash; Source: Esri",
        maxNativeZoom: 18,
        maxZoom: 22,
      }
    );

    streetLayer.addTo(map);

    // Register click event on map to select GPS destination target
    map.on("click", (e: L.LeafletMouseEvent) => {
      const clickedLat = Number(e.latlng.lat.toFixed(6));
      const clickedLon = Number(e.latlng.lng.toFixed(6));
      if (onSelectTargetRef.current) {
        onSelectTargetRef.current({ lat: clickedLat, lon: clickedLon });
      }
    });

    // Store layers for switching
    (map as any)._streetLayer = streetLayer;
    (map as any)._satelliteLayer = satelliteLayer;

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // State for map style & container height
  const [isSatellite, setIsSatellite] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  // Toggle Satellite / Street tile layer
  const toggleMapStyle = () => {
    const map = mapInstanceRef.current as any;
    if (!map) return;
    if (isSatellite) {
      map.removeLayer(map._satelliteLayer);
      map._streetLayer.addTo(map);
      setIsSatellite(false);
    } else {
      map.removeLayer(map._streetLayer);
      map._satelliteLayer.addTo(map);
      setIsSatellite(true);
    }
  };

  // Quick zoom in to Drone position or Center at max zoom 20x
  const handleZoomCloseIn = () => {
    const map = mapInstanceRef.current;
    if (!map) return;
    if (telemetry?.latitude && telemetry?.longitude && telemetry.latitude !== 0) {
      map.setView([telemetry.latitude, telemetry.longitude], 20, { animate: true });
    } else if (locations.home_lat && locations.home_lon) {
      map.setView([locations.home_lat, locations.home_lon], 20, { animate: true });
    } else {
      map.setZoom(20, { animate: true });
    }
  };

  // Update Mission Locations (Home, Pickup, Drop Markers & Planned Path)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // 1. Home / Warehouse Marker (Saved on ARM)
    if (locations.home_lat && locations.home_lon) {
      const pos: [number, number] = [locations.home_lat, locations.home_lon];
      const popupText = `
        <div style="font-family: sans-serif; font-size: 12px; line-height: 1.5;">
          <strong style="color: #3b82f6;">🏠 Vị trí Home (ARM)</strong><br/>
          <b>Lat:</b> ${locations.home_lat.toFixed(6)}<br/>
          <b>Lon:</b> ${locations.home_lon.toFixed(6)}
        </div>
      `;
      if (!homeMarkerRef.current) {
        homeMarkerRef.current = L.marker(pos, {
          icon: createCustomIcon("🏠", "#3b82f6", "Home (ARM)"),
        })
          .bindPopup(popupText)
          .addTo(map);
      } else {
        homeMarkerRef.current.setLatLng(pos);
        homeMarkerRef.current.setPopupContent(popupText);
      }
    } else if (homeMarkerRef.current) {
      homeMarkerRef.current.remove();
      homeMarkerRef.current = null;
    }

    // 2. Pickup Location Marker
    if (locations.pickup_lat && locations.pickup_lon) {
      const pos: [number, number] = [locations.pickup_lat, locations.pickup_lon];
      if (!pickupMarkerRef.current) {
        pickupMarkerRef.current = L.marker(pos, {
          icon: createCustomIcon("📦", "#f59e0b", "Điểm lấy hàng"),
        })
          .bindPopup("<b>📦 Điểm Lấy Hàng (Pickup)</b>")
          .addTo(map);
      } else {
        pickupMarkerRef.current.setLatLng(pos);
      }
    } else if (pickupMarkerRef.current) {
      pickupMarkerRef.current.remove();
      pickupMarkerRef.current = null;
    }

    // 3. Dropoff Location Marker
    if (locations.drop_lat && locations.drop_lon) {
      const pos: [number, number] = [locations.drop_lat, locations.drop_lon];
      if (!dropMarkerRef.current) {
        dropMarkerRef.current = L.marker(pos, {
          icon: createCustomIcon("📍", "#ef4444", "Điểm giao"),
        })
          .bindPopup("<b>📍 Điểm Giao Hàng (Drop-off)</b>")
          .addTo(map);
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

  // Update Drone Telemetry Marker & Flight Trail (High-performance optimized)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !telemetry || !droneOnline) return;

    const lat = telemetry.latitude;
    const lon = telemetry.longitude;

    if (!lat || !lon || (lat === 0 && lon === 0)) return;

    const dronePos: [number, number] = [lat, lon];
    const heading = Math.round(telemetry.heading || 0);

    // Update or Create Drone Marker
    if (!droneMarkerRef.current) {
      lastHeadingRef.current = heading;
      droneMarkerRef.current = L.marker(dronePos, {
        icon: createCustomIcon("🛸", "#10b981", "Drone", heading),
        zIndexOffset: 1000,
      }).addTo(map);
    } else {
      droneMarkerRef.current.setLatLng(dronePos);
      // Only recreate divIcon if heading rotated by more than 4 degrees
      if (Math.abs(heading - lastHeadingRef.current) >= 4) {
        lastHeadingRef.current = heading;
        droneMarkerRef.current.setIcon(createCustomIcon("🛸", "#10b981", "Drone", heading));
      }
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

    // Auto-center map on drone smoothly without animation interruption
    if (followDrone) {
      const now = Date.now();
      if (now - lastPanTimeRef.current > 500) {
        lastPanTimeRef.current = now;
        map.panTo(dronePos, { animate: false });
      }
    }

    // Append to flight history trail directly on polyline without full re-render
    const pts = trailPointsRef.current;
    const lastPoint = pts[pts.length - 1];
    if (!lastPoint || Math.abs(lastPoint[0] - lat) > 0.00001 || Math.abs(lastPoint[1] - lon) > 0.00001) {
      pts.push(dronePos);
      if (pts.length > 500) pts.shift();

      if (pts.length >= 2) {
        if (!flightTrailRef.current) {
          flightTrailRef.current = L.polyline(pts, {
            color: "#10b981",
            weight: 4,
            opacity: 0.85,
          }).addTo(map);
        } else {
          flightTrailRef.current.setLatLngs(pts);
        }
      }
    }
  }, [telemetry, droneOnline, followDrone]);

  // Update Target Selected Marker & Guidance Line
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (selectedTarget && selectedTarget.lat && selectedTarget.lon) {
      const pos: [number, number] = [selectedTarget.lat, selectedTarget.lon];
      if (!targetMarkerRef.current) {
        targetMarkerRef.current = L.marker(pos, {
          icon: createCustomIcon("🎯", "#00F0FF", "Đích đến GPS"),
          zIndexOffset: 1200,
        })
          .bindPopup(
            `<b>🎯 Điểm Đến Đã Chọn (NAV_GPS)</b><br/>Lat: ${selectedTarget.lat.toFixed(6)}<br/>Lon: ${selectedTarget.lon.toFixed(6)}`
          )
          .addTo(map);
      } else {
        targetMarkerRef.current.setLatLng(pos);
        targetMarkerRef.current.setPopupContent(
          `<b>🎯 Điểm Đến Đã Chọn (NAV_GPS)</b><br/>Lat: ${selectedTarget.lat.toFixed(6)}<br/>Lon: ${selectedTarget.lon.toFixed(6)}`
        );
      }

      // Guidance line from drone or home to target
      const startPos: [number, number] | null =
        telemetry?.latitude && telemetry?.longitude && telemetry.latitude !== 0
          ? [telemetry.latitude, telemetry.longitude]
          : locations.home_lat && locations.home_lon
          ? [locations.home_lat, locations.home_lon]
          : null;

      if (startPos) {
        if (!targetLineRef.current) {
          targetLineRef.current = L.polyline([startPos, pos], {
            color: "#00F0FF",
            weight: 3,
            dashArray: "6, 6",
            opacity: 0.9,
          }).addTo(map);
        } else {
          targetLineRef.current.setLatLngs([startPos, pos]);
        }
      }
    } else {
      if (targetMarkerRef.current) {
        targetMarkerRef.current.remove();
        targetMarkerRef.current = null;
      }
      if (targetLineRef.current) {
        targetLineRef.current.remove();
        targetLineRef.current = null;
      }
    }
  }, [selectedTarget, telemetry, locations]);

  // Fit view bounds to contain all active markers
  const handleFitBounds = () => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const bounds = L.latLngBounds([]);
    if (locations.home_lat && locations.home_lon) bounds.extend([locations.home_lat, locations.home_lon]);
    if (locations.pickup_lat && locations.pickup_lon) bounds.extend([locations.pickup_lat, locations.pickup_lon]);
    if (locations.drop_lat && locations.drop_lon) bounds.extend([locations.drop_lat, locations.drop_lon]);
    if (selectedTarget?.lat && selectedTarget?.lon) bounds.extend([selectedTarget.lat, selectedTarget.lon]);
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
          {selectedTarget && (
            <span
              style={{
                marginLeft: "8px",
                fontSize: "11px",
                color: "#00F0FF",
                background: "rgba(0, 240, 255, 0.15)",
                padding: "2px 6px",
                borderRadius: "4px",
                border: "1px solid rgba(0, 240, 255, 0.3)",
              }}
            >
              🎯 Đích: {selectedTarget.lat.toFixed(5)}, {selectedTarget.lon.toFixed(5)}
            </span>
          )}
        </div>

        <div className="map-toolbar-actions">
          {selectedTarget && (
            <button
              type="button"
              className="btn-map-action active"
              style={{ borderColor: "#00F0FF", color: "#00F0FF", background: "rgba(0, 240, 255, 0.2)" }}
              onClick={() => onSelectTargetRef.current?.(null)}
              title="Xóa điểm đích đã chọn"
            >
              ❌ Bỏ chọn đích
            </button>
          )}
          <button
            type="button"
            className={`btn-map-action ${isSatellite ? "active" : ""}`}
            onClick={toggleMapStyle}
            title="Chuyển đổi Bản đồ Vệ tinh / Đô thị"
          >
            {isSatellite ? "🗺️ Đô thị" : "🛰️ Vệ tinh"}
          </button>
          <button
            type="button"
            className="btn-map-action"
            onClick={handleZoomCloseIn}
            title="Phóng to siêu cận cảnh Drone (Zoom 20x)"
          >
            🔬 Zoom cận cảnh (20x)
          </button>
          <button
            type="button"
            className={`btn-map-action ${followDrone ? "active" : ""}`}
            onClick={() => setFollowDrone(!followDrone)}
            title="Tự động cuộn bản đồ theo vị trí Drone"
          >
            🎯 {followDrone ? "Theo dõi ON" : "Theo dõi OFF"}
          </button>
          <button
            type="button"
            className="btn-map-action"
            onClick={handleFitBounds}
            title="Zoom hiển thị toàn bộ lộ trình"
          >
            🌐 Zoom toàn bộ
          </button>
          <button
            type="button"
            className="btn-map-action"
            onClick={() => setIsExpanded(!isExpanded)}
            title="Mở rộng chiều cao bản đồ"
          >
            {isExpanded ? "📐 Thu nhỏ chiều cao" : "↕️ Mở rộng bản đồ"}
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

      {/* Map Click Hint Banner */}
      <div
        style={{
          position: "absolute",
          top: "48px",
          left: "12px",
          zIndex: 500,
          background: "rgba(15, 23, 42, 0.85)",
          color: selectedTarget ? "#00F0FF" : "#cbd5e1",
          padding: "4px 8px",
          borderRadius: "4px",
          fontSize: "11px",
          border: selectedTarget ? "1px solid rgba(0, 240, 255, 0.4)" : "1px solid rgba(255, 255, 255, 0.1)",
          backdropFilter: "blur(4px)",
          pointerEvents: "none",
        }}
      >
        {selectedTarget ? (
          <span>🎯 Đã chọn đích: <b>{selectedTarget.lat.toFixed(6)}, {selectedTarget.lon.toFixed(6)}</b> (Bấm bước 4 để bay)</span>
        ) : (
          <span>💡 <i>Click bất kỳ điểm nào trên bản đồ để chọn tọa độ đích cho bước <b>BAY GPS</b></i></span>
        )}
      </div>

      {/* Main Leaflet Container */}
      <div
        ref={mapContainerRef}
        className="map-container-box"
        style={{
          width: "100%",
          height: isExpanded ? "750px" : "550px",
          transition: "height 0.3s ease",
        }}
      />

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
});
