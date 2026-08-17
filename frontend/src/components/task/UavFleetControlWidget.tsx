import { useState, useEffect, useCallback } from "react";
import {
  getFleetStatus,
  signalDroneArrived,
  signalDroneDepartHome,
  signalDroneDepartDelivery,
  setDroneFlightMode,
  startSystemAuto,
} from "../../services/api";

export interface FleetUnit {
  drone_id: string;
  is_real: boolean;
  flight_mode: "AUTO" | "MANUAL";
  state:
    | "READY"
    | "FLYING_TO_WAREHOUSE"
    | "LANDED"
    | "LOADING"
    | "READY_TO_DEPART_HOME"
    | "READY_TO_DEPART_DELIVERY"
    | "FLYING_DELIVERY"
    | "RETURN_HOME"
    | "OFFLINE";
  battery: number;
  latitude: number;
  longitude: number;
  altitude_agl: number;
  current_mission_id?: number | null;
  last_updated?: string;
}

interface Props {
  activeMissionDroneId?: string;
  activeMissionType?: "DRONE_PICKUP" | "DRONE_DELIVERY" | null;
  onRefreshQueue?: () => void;
}

export function UavFleetControlWidget({
  activeMissionDroneId,
  activeMissionType: _activeMissionType,
  onRefreshQueue,
}: Props) {
  const [fleet, setFleet] = useState<FleetUnit[]>([
    {
      drone_id: "UAV01",
      is_real: true,
      flight_mode: "AUTO",
      state: "READY",
      battery: 95.0,
      latitude: 16.0544,
      longitude: 108.2022,
      altitude_agl: 0.0,
    },
    {
      drone_id: "UAV02",
      is_real: false,
      flight_mode: "AUTO",
      state: "READY",
      battery: 98.0,
      latitude: 16.0545,
      longitude: 108.2025,
      altitude_agl: 0.0,
    },
    {
      drone_id: "UAV03",
      is_real: false,
      flight_mode: "AUTO",
      state: "READY",
      battery: 100.0,
      latitude: 16.0546,
      longitude: 108.2028,
      altitude_agl: 0.0,
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<{ text: string; isError: boolean } | null>(null);

  const fetchFleet = useCallback(async () => {
    try {
      const res = await getFleetStatus();
      if (res.ok) {
        const data = await res.json();
        if (data.fleet && Array.isArray(data.fleet)) {
          setFleet(data.fleet);
        }
      }
    } catch {
      // Ignore polling errors
    }
  }, []);

  useEffect(() => {
    fetchFleet();
    const interval = setInterval(fetchFleet, 3000);

    const handleFleetUpdate = (e: any) => {
      if (e.detail?.fleet) {
        setFleet(e.detail.fleet);
      } else {
        fetchFleet();
      }
    };

    window.addEventListener("fleet_update", handleFleetUpdate);
    return () => {
      clearInterval(interval);
      window.removeEventListener("fleet_update", handleFleetUpdate);
    };
  }, [fetchFleet]);

  const handleAutoStartSystem = async () => {
    setLoading(true);
    setActionMsg(null);
    try {
      const res = await startSystemAuto();
      if (res.ok) {
        const data = await res.json();
        setActionMsg({ text: `⚡ ${data.message}`, isError: false });
        fetchFleet();
        if (onRefreshQueue) onRefreshQueue();
      } else {
        const err = await res.json();
        setActionMsg({ text: `❌ Lỗi khởi động: ${err.detail || "Thất bại"}`, isError: true });
      }
    } catch {
      setActionMsg({ text: "❌ Lỗi kết nối server khi khởi động hệ thống", isError: true });
    } finally {
      setLoading(false);
    }
  };

  const handleSignalArrive = async (droneId: string) => {
    setActionMsg(null);
    try {
      const res = await signalDroneArrived(droneId);
      if (res.ok) {
        setActionMsg({ text: `🛬 Đã kích hoạt: ${droneId} đã tiếp đất tại Trạm N1 (PLC Lock & Robot Start)!`, isError: false });
        fetchFleet();
        if (onRefreshQueue) onRefreshQueue();
      }
    } catch {
      setActionMsg({ text: `❌ Lỗi gửi tín hiệu đáp cho ${droneId}`, isError: true });
    }
  };

  const handleSignalDepartHome = async (droneId: string) => {
    setActionMsg(null);
    try {
      const res = await signalDroneDepartHome(droneId);
      if (res.ok) {
        setActionMsg({ text: `🛫 Đã kích hoạt: ${droneId} cất cánh về Home. Bãi đáp N1 đã sẵn sàng cho đơn tiếp theo!`, isError: false });
        fetchFleet();
        if (onRefreshQueue) onRefreshQueue();
      }
    } catch {
      setActionMsg({ text: `❌ Lỗi gửi tín hiệu về Home cho ${droneId}`, isError: true });
    }
  };

  const handleSignalDepartDelivery = async (droneId: string) => {
    setActionMsg(null);
    try {
      const res = await signalDroneDepartDelivery(droneId);
      if (res.ok) {
        setActionMsg({ text: `🚀 Đã kích hoạt: ${droneId} nhận hàng và cất cánh bay đi giao cho khách!`, isError: false });
        fetchFleet();
        if (onRefreshQueue) onRefreshQueue();
      }
    } catch {
      setActionMsg({ text: `❌ Lỗi gửi tín hiệu đi giao cho ${droneId}`, isError: true });
    }
  };

  const handleToggleFlightMode = async (droneId: string, currentMode: "AUTO" | "MANUAL") => {
    const newMode = currentMode === "AUTO" ? "MANUAL" : "AUTO";
    try {
      await setDroneFlightMode(droneId, newMode);
      fetchFleet();
    } catch {
      // Ignore
    }
  };

  const getStateBadgeClass = (state: string) => {
    switch (state) {
      case "READY":
        return "badge-ready";
      case "FLYING_TO_WAREHOUSE":
      case "FLYING_DELIVERY":
      case "RETURN_HOME":
        return "badge-flying";
      case "LANDED":
      case "LOADING":
        return "badge-landed";
      case "READY_TO_DEPART_HOME":
      case "READY_TO_DEPART_DELIVERY":
        return "badge-depart-ready";
      default:
        return "badge-offline";
    }
  };

  const formatStateText = (state: string) => {
    switch (state) {
      case "READY":
        return "SẴN SÀNG (READY)";
      case "FLYING_TO_WAREHOUSE":
        return "BAY VỀ TRẠM (EN ROUTE)";
      case "LANDED":
        return "ĐÃ TIẾP ĐẤT (LANDED)";
      case "LOADING":
        return "KHO ĐANG XỬ LÝ (LOADING)";
      case "READY_TO_DEPART_HOME":
        return "DỠ XONG - CHỜ VỀ HOME";
      case "READY_TO_DEPART_DELIVERY":
        return "NẠP XONG - CHỜ ĐI GIAO";
      case "FLYING_DELIVERY":
        return "BAY ĐI GIAO HÀNG";
      case "RETURN_HOME":
        return "BAY VỀ HOME";
      default:
        return state;
    }
  };

  // Find priority actionable UAVs
  const activeUav = fleet.find((u) => u.drone_id === activeMissionDroneId) || fleet[0];

  return (
    <div className="uav-fleet-widget-container hmi-card">
      <div className="card-header flex-between">
        <div className="fleet-title-row">
          <h3>🚁 UAV FLEET CONTROLLER & HANDSHAKE SIMULATION</h3>
          <span className="subtitle">Quản lý Đội bay & Kích hoạt Tín hiệu UAV Đến / Đi theo thời gian thực</span>
        </div>
        <button
          type="button"
          className="btn-hmi btn-auto-start"
          onClick={handleAutoStartSystem}
          disabled={loading}
          title="Kiểm tra kết nối thiết bị & Quét hàng chờ tự động thực thi"
        >
          {loading ? "⟳ Đang khởi động..." : "⚡ KHỞI ĐỘNG HỆ THỐNG LIÊN HOÀN (AUTO RUN)"}
        </button>
      </div>

      {actionMsg && (
        <div className={`status-msg-banner ${actionMsg.isError ? "error" : "success"}`} style={{ margin: "0.5rem 1rem" }}>
          {actionMsg.text}
        </div>
      )}

      {/* Dynamic Contextual Action Bar */}
      <div className="fleet-context-action-bar">
        <div className="context-action-header">
          <span className="pulse-indicator"></span>
          <strong>HÀNH ĐỘNG MÔ PHỎNG THEO TIẾN ĐỘ ĐƠN HÀNG (SIMULATION TRIGGERS):</strong>
        </div>

        <div className="context-buttons-row">
          {/* Simulation button for Drone Arrival */}
          <button
            type="button"
            className="btn-hmi btn-action-arrive"
            onClick={() => handleSignalArrive(activeUav.drone_id)}
            title="Mô phỏng UAV đã hạ cánh tại bãi đáp N1"
          >
            🛬 MÔ PHỎNG [{activeUav.drone_id}] ĐÃ ĐÁP TẠI TRẠM N1
          </button>

          {/* Simulation button for Drone Depart Home */}
          <button
            type="button"
            className="btn-hmi btn-action-depart-home"
            onClick={() => handleSignalDepartHome(activeUav.drone_id)}
            title="Mô phỏng UAV dỡ hàng xong và cất cánh về Home (giải phóng bãi đáp)"
          >
            🛫 MÔ PHỎNG [{activeUav.drone_id}] CẤT CÁNH VỀ HOME
          </button>

          {/* Simulation button for Drone Depart Delivery */}
          <button
            type="button"
            className="btn-hmi btn-action-depart-delivery"
            onClick={() => handleSignalDepartDelivery(activeUav.drone_id)}
            title="Mô phỏng UAV nhận hàng và cất cánh đi giao hàng cho khách"
          >
            🚀 MÔ PHỎNG [{activeUav.drone_id}] CẤT CÁNH ĐI GIAO HÀNG
          </button>
        </div>
      </div>

      {/* UAV Fleet Cards List */}
      <div className="fleet-cards-grid">
        {fleet.map((uav) => {
          const isAssigned = uav.drone_id === activeMissionDroneId;
          return (
            <div
              key={uav.drone_id}
              className={`uav-fleet-card ${uav.is_real ? "real-uav" : "sim-uav"} ${isAssigned ? "assigned-active" : ""}`}
            >
              <div className="uav-card-top flex-between">
                <div className="uav-id-badge">
                  <span className="uav-name">{uav.drone_id}</span>
                  <span className={`uav-type-tag ${uav.is_real ? "type-real" : "type-sim"}`}>
                    {uav.is_real ? "REAL HARDWARE" : "VIRTUAL FLEET"}
                  </span>
                </div>
                <div className="uav-mode-badge">
                  {uav.is_real ? (
                    <button
                      type="button"
                      className={`btn-mode-toggle ${uav.flight_mode.toLowerCase()}`}
                      onClick={() => handleToggleFlightMode(uav.drone_id, uav.flight_mode)}
                      title="Chuyển đổi Chế độ Bay AUTO / MANUAL"
                    >
                      {uav.flight_mode === "AUTO" ? "🤖 AUTO" : "🎮 MANUAL"}
                    </button>
                  ) : (
                    <span className="mode-auto-tag">🤖 AUTO</span>
                  )}
                </div>
              </div>

              <div className="uav-card-status-row">
                <span className={`uav-status-pill ${getStateBadgeClass(uav.state)}`}>
                  ● {formatStateText(uav.state)}
                </span>
                {uav.current_mission_id && (
                  <span className="uav-mission-ref font-mono text-cyan">
                    Mission #{uav.current_mission_id}
                  </span>
                )}
              </div>

              <div className="uav-telemetry-mini-grid">
                <div className="mini-cell">
                  <span className="lbl">Pin (Battery):</span>
                  <span className="val text-emerald font-mono">{uav.battery}%</span>
                </div>
                <div className="mini-cell">
                  <span className="lbl">Độ cao AGL:</span>
                  <span className="val font-mono">{uav.altitude_agl.toFixed(1)}m</span>
                </div>
              </div>

              {/* Individual quick triggers */}
              <div className="uav-quick-actions flex-between">
                <button
                  type="button"
                  className="btn-mini-trigger"
                  onClick={() => handleSignalArrive(uav.drone_id)}
                  title="Báo đáp bãi N1"
                >
                  🛬 Đáp N1
                </button>
                <button
                  type="button"
                  className="btn-mini-trigger"
                  onClick={() => handleSignalDepartHome(uav.drone_id)}
                  title="Báo về Home"
                >
                  🛫 Về Home
                </button>
                <button
                  type="button"
                  className="btn-mini-trigger"
                  onClick={() => handleSignalDepartDelivery(uav.drone_id)}
                  title="Báo đi giao"
                >
                  🚀 Đi Giao
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
