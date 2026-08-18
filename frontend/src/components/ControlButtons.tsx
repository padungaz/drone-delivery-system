import { useState } from "react";
import type { MissionLocations, Telemetry } from "../types/drone";
import {
  DROP_OK_ENABLED_STATES,
  FLYING_STATES,
  PICKUP_OK_ENABLED_STATES,
} from "../types/drone";
import {
  dropComplete,
  forceRtl,
  pickupComplete,
  stopMission,
} from "../services/api";

interface Props {
  locations: MissionLocations;
  telemetry: Telemetry | null;
  droneOnline: boolean;
  onOpenManual: () => void;
}

type Action = "pickup_ok" | "drop_ok" | "rtl" | "stop";

// Status banner configs per drone state
const STATE_BANNERS: Record<string, { text: string; cls: string }> = {
  WAIT_PICKUP_CONFIRM: {
    text: "📦 Đã tiếp đất điểm Lấy hàng — nhấn XÁC NHẬN LẤY HÀNG (PICKUP OK) khi hàng đã gài an toàn",
    cls: "banner-pickup",
  },
  WAIT_DROP_CONFIRM: {
    text: "📬 Đã tiếp đất điểm Giao hàng — nhấn XÁC NHẬN GIAO HÀNG (DROP OK) để hoàn tất",
    cls: "banner-drop",
  },
  RETURN_HOME: {
    text: "🏠 Drone đang quay về Trạm xuất phát",
    cls: "banner-rtl",
  },
  ERROR: {
    text: "⚠️ Lỗi FSM Drone — kiểm tra logs companion hoặc nhấn Reset IDLE trong Manual Mode.",
    cls: "banner-error",
  },
};

export function ControlButtons({ locations, telemetry, droneOnline, onOpenManual }: Props) {
  const [loading, setLoading] = useState<Action | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const state = telemetry?.drone_state ?? null;

  // ── Button enable logic ────────────────────────────────────────────────
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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h2>🎮 UAV Flight Controls</h2>
        <span className={`badge ${droneOnline ? "online" : "offline"}`}>
          {droneOnline ? "DRONE ONLINE" : "DRONE OFFLINE"}
        </span>
      </div>

      {/* Contextual status banner */}
      {banner && (
        <div className={`state-banner ${banner.cls}`}>
          {banner.text}
        </div>
      )}

      {/* Row 1: Manual flight mode modal trigger & emergency flight commands */}
      <div className="button-row" style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
        <button
          onClick={onOpenManual}
          className="btn btn-secondary"
          style={{ flex: "1.2", background: "linear-gradient(135deg, #1e293b, #0f172a)", borderColor: "#00F0FF", color: "#00F0FF", fontWeight: "bold" }}
          title="Mở bảng điều khiển kiểm thử thủ công: ARM, Disarm, Chế độ bay, Quy trình 7 bước"
        >
          🎮 Bảng Điều Khiển Thủ Công (Manual Mode)
        </button>

        <button
          id="btn-force-rtl"
          className="btn btn-rtl"
          disabled={!canRtl || loading !== null}
          onClick={() => handleAction("rtl")}
          title="Khẩn cấp: Yêu cầu Drone quay về trạm xuất phát lập tức"
        >
          {loading === "rtl" ? "Sending…" : "🏠 FORCE RETURN HOME"}
        </button>

        <button
          id="btn-stop"
          className="btn btn-stop"
          disabled={!canStop || loading !== null}
          onClick={() => handleAction("stop")}
          title={
            !canStop
              ? "DỪNG/RESET chỉ khả dụng khi Drone đã tiếp đất & Disarmed"
              : "Reset FSM về IDLE"
          }
        >
          {loading === "stop" ? "Sending…" : "⏹ STOP / RESET"}
        </button>
      </div>

      {/* Row 2: User confirmation gates on ground */}
      <div className="button-row" style={{ display: "flex", gap: "8px" }}>
        <button
          id="btn-pickup-ok"
          className="btn btn-pickup-ok"
          style={{ flex: 1 }}
          disabled={!canPickupOk || loading !== null}
          onClick={() => handleAction("pickup_ok")}
          title={
            !canPickupOk
              ? "Chỉ khả dụng khi Drone đang ở điểm lấy hàng (WAIT_PICKUP_CONFIRM)"
              : "Xác nhận hàng đã được gài chắc chắn trên Drone"
          }
        >
          {loading === "pickup_ok" ? "Sending…" : "📦 XÁC NHẬN LẤY HÀNG (PICKUP OK)"}
        </button>

        <button
          id="btn-drop-ok"
          className="btn btn-drop-ok"
          style={{ flex: 1 }}
          disabled={!canDropOk || loading !== null}
          onClick={() => handleAction("drop_ok")}
          title={
            !canDropOk
              ? "Chỉ khả dụng khi Drone đang ở điểm giao hàng (WAIT_DROP_CONFIRM)"
              : "Xác nhận hàng đã giao an toàn cho khách"
          }
        >
          {loading === "drop_ok" ? "Sending…" : "📬 XÁC NHẬN GIAO HÀNG (DROP OK)"}
        </button>
      </div>

      {/* Response message */}
      {message && <p className="action-message" style={{ marginTop: "8px" }}>{message}</p>}

      {/* State hint */}
      {telemetry && (
        <p className="muted hint" style={{ marginTop: "8px" }}>
          State: <strong>{telemetry.drone_state}</strong>
          {" · "}Phase: {telemetry.landing_phase || "—"}
          {" · "}Armed: {telemetry.armed ? "YES" : "NO"}
          {" · "}Mode: <strong>{telemetry.flight_mode}</strong>
        </p>
      )}
    </section>
  );
}
