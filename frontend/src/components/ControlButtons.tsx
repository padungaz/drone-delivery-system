import { useState } from "react";
import type { MissionLocations, Telemetry } from "../types/drone";
import {
  DROP_OK_ENABLED_STATES,
  FLYING_STATES,
  PICKUP_OK_ENABLED_STATES,
  START_ENABLED_STATES,
} from "../types/drone";
import {
  dropComplete,
  forceRtl,
  pickupComplete,
  startMission,
  stopMission,
} from "../services/api";

interface Props {
  locations: MissionLocations;
  telemetry: Telemetry | null;
  droneOnline: boolean;
  onOpenManual: () => void;
}

type Action = "start" | "pickup_ok" | "drop_ok" | "rtl" | "stop";

// Status banner configs per drone state
const STATE_BANNERS: Record<string, { text: string; cls: string }> = {
  WAIT_PICKUP_CONFIRM: {
    text: "📦 Package ready at pickup location — press PICKUP OK when package is secured",
    cls: "banner-pickup",
  },
  WAIT_DROP_CONFIRM: {
    text: "📬 Package delivered at drop location — press DROP OK to confirm delivery",
    cls: "banner-drop",
  },
  RETURN_HOME: {
    text: "🏠 Returning home — START is available for the next delivery",
    cls: "banner-rtl",
  },
  ERROR: {
    text: "⚠️ Drone error — check companion logs. Will auto-recover to IDLE.",
    cls: "banner-error",
  },
};

export function ControlButtons({ locations, telemetry, droneOnline, onOpenManual }: Props) {
  const [loading, setLoading] = useState<Action | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const state = telemetry?.drone_state ?? null;

  // ── Button enable logic ────────────────────────────────────────────────
  const canStart = droneOnline && state != null && START_ENABLED_STATES.has(state);
  const canPickupOk = droneOnline && state != null && PICKUP_OK_ENABLED_STATES.has(state);
  const canDropOk = droneOnline && state != null && DROP_OK_ENABLED_STATES.has(state);
  const canRtl = droneOnline && state != null && FLYING_STATES.has(state);
  const canStop =
    droneOnline &&
    state != null &&
    !telemetry?.armed &&
    state !== "IDLE";

  // ── Action handler ─────────────────────────────────────────────────────
  const handleAction = async (action: Action) => {
    setLoading(action);
    setMessage(null);
    try {
      let res: Response;
      switch (action) {
        case "start":      res = await startMission(locations);   break;
        case "pickup_ok":  res = await pickupComplete(locations); break;
        case "drop_ok":    res = await dropComplete(locations);   break;
        case "rtl":        res = await forceRtl(locations);       break;
        case "stop":       res = await stopMission(locations);    break;
      }
      const data = await res.json();
      if (!res.ok) {
        setMessage(`Error: ${data.detail ?? "Request failed"}`);
      } else {
        setMessage(data.status ?? "OK");
      }
    } catch (err) {
      setMessage(`Error: ${err instanceof Error ? err.message : "Network error"}`);
    } finally {
      setLoading(null);
    }
  };

  // ── Status banner ──────────────────────────────────────────────────────
  const banner = state != null ? STATE_BANNERS[state] ?? null : null;

  return (
    <section className="panel control-buttons">
      <h2>Controls</h2>

      {/* Contextual status banner */}
      {banner && (
        <div className={`state-banner ${banner.cls}`}>
          {banner.text}
        </div>
      )}

      {/* Row 1: primary mission controls */}
      <div className="button-row">
        <button
          onClick={onOpenManual}
          className="btn btn-secondary"
          title="Open manual control interface"
        >
          🎮 Manual Mode
        </button>

        <button
          id="btn-start-mission"
          className="btn btn-start"
          disabled={!canStart || loading !== null}
          onClick={() => handleAction("start")}
          title={
            !canStart
              ? `START requires IDLE or RETURN_HOME state (current: ${state ?? "offline"})`
              : state === "RETURN_HOME"
              ? "Queue next delivery (Continuous Delivery Mode)"
              : "Start delivery mission"
          }
        >
          {loading === "start" ? "Sending…" : "▶ START MISSION"}
        </button>

        <button
          id="btn-force-rtl"
          className="btn btn-rtl"
          disabled={!canRtl || loading !== null}
          onClick={() => handleAction("rtl")}
          title="Emergency: force drone to return home immediately"
        >
          {loading === "rtl" ? "Sending…" : "🏠 FORCE RETURN HOME"}
        </button>
      </div>

      {/* Row 2: user confirm gates */}
      <div className="button-row">
        <button
          id="btn-pickup-ok"
          className="btn btn-pickup-ok"
          disabled={!canPickupOk || loading !== null}
          onClick={() => handleAction("pickup_ok")}
          title={
            !canPickupOk
              ? "Only available when drone has landed at pickup (WAIT_PICKUP_CONFIRM)"
              : "Confirm package has been secured — drone will proceed to drop"
          }
        >
          {loading === "pickup_ok" ? "Sending…" : "📦 PICKUP OK"}
        </button>

        <button
          id="btn-drop-ok"
          className="btn btn-drop-ok"
          disabled={!canDropOk || loading !== null}
          onClick={() => handleAction("drop_ok")}
          title={
            !canDropOk
              ? "Only available when drone has landed at drop (WAIT_DROP_CONFIRM)"
              : "Confirm package delivered — drone will return home"
          }
        >
          {loading === "drop_ok" ? "Sending…" : "📬 DROP OK"}
        </button>

        <button
          id="btn-stop"
          className="btn btn-stop"
          disabled={!canStop || loading !== null}
          onClick={() => handleAction("stop")}
          title={
            !canStop
              ? "STOP only when on ground + disarmed (not IDLE)"
              : "Stop mission and reset drone to IDLE"
          }
        >
          {loading === "stop" ? "Sending…" : "⏹ STOP"}
        </button>
      </div>

      {/* Response message */}
      {message && <p className="action-message">{message}</p>}

      {/* State hint */}
      {telemetry && (
        <p className="muted hint">
          State: <strong>{telemetry.drone_state}</strong>
          {" · "}Phase: {telemetry.landing_phase || "—"}
          {" · "}Armed: {telemetry.armed ? "YES" : "NO"}
        </p>
      )}
    </section>
  );
}
