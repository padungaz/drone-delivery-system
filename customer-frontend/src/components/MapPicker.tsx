import { useEffect, useRef, useState } from "react";
import type { LatLon } from "../types/customer";

interface Props {
  initialLat?: number;
  initialLon?: number;
  onSelect: (pos: LatLon) => void;
  label?: string;
}

declare global {
  interface Window {
    L: typeof import("leaflet");
  }
}

export function MapPicker({ initialLat, initialLon, onSelect, label }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const [selected, setSelected] = useState<LatLon | null>(
    initialLat && initialLon ? { lat: initialLat, lon: initialLon } : null,
  );

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;
    const L = window.L;
    if (!L) return;

    const defaultLat = initialLat ?? 16.0544;
    const defaultLon = initialLon ?? 108.2022;

    const map = L.map(mapRef.current, {
      center: [defaultLat, defaultLon],
      zoom: 15,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
    }).addTo(map);

    if (initialLat && initialLon) {
      const m = L.marker([initialLat, initialLon]).addTo(map);
      markerRef.current = m;
    }

    map.on("click", (e: any) => {
      const { lat, lng } = e.latlng;
      const pos: LatLon = { lat, lon: lng };
      setSelected(pos);
      onSelect(pos);

      if (markerRef.current) {
        markerRef.current.setLatLng([lat, lng]);
      } else {
        markerRef.current = L.marker([lat, lng]).addTo(map);
      }
    });

    mapInstance.current = map;

    return () => {
      map.remove();
      mapInstance.current = null;
      markerRef.current = null;
    };
  }, []);

  return (
    <div>
      {label && <p className="form-hint" style={{ marginBottom: "0.35rem" }}>{label}</p>}
      <div ref={mapRef} className="map-container" />
      <p className="map-hint">Nhấn vào bản đồ để chọn điểm</p>
      {selected && (
        <div className="selected-coords">
          <div className="coords-dot" />
          <span>
            {selected.lat.toFixed(7)}, {selected.lon.toFixed(7)}
          </span>
        </div>
      )}
    </div>
  );
}
