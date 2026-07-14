import { useState } from "react";
import type { MissionLocations } from "../types/drone";

interface Props {
  onChange: (locations: MissionLocations) => void;
}

const DEFAULT_LOCATIONS: MissionLocations = {
  home_lat: 21.0285,
  home_lon: 105.8542,
  pickup_lat: 21.0290,
  pickup_lon: 105.8550,
  drop_lat: 21.0275,
  drop_lon: 105.8530,
};

export function MissionForm({ onChange }: Props) {
  const [locations, setLocations] = useState<MissionLocations>(DEFAULT_LOCATIONS);

  const update = (field: keyof MissionLocations, value: string) => {
    const next = { ...locations, [field]: parseFloat(value) || 0 };
    setLocations(next);
    onChange(next);
  };

  return (
    <section className="panel mission-form">
      <h2>Mission Locations</h2>
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
    </section>
  );
}
