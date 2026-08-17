import { useState, useEffect } from "react";
import type {
  DeviceInfo,
  PLCState,
  RobotState,
  StorageSlot,
  DeviceCommandLog,
  IntralogisticsMission,
  StationOperation,
} from "../types/drone";
import { DeviceStatusPanel } from "./DeviceStatusPanel";
import { PlcControlPanel } from "./PlcControlPanel";
import { RobotControlPanel } from "./RobotControlPanel";
import { StorageSlotsGrid } from "./StorageSlotsGrid";
import { DeviceConfigModal } from "./DeviceConfigModal";
import {
  startDeviceCamera,
  stopDeviceCamera,
  testDeviceCameraQr,
  getDeviceLogs,
  startIntralogisticsMission,
  pauseMission,
  resumeMission,
  triggerAutoStartMissions,
  API_BASE,
} from "../services/api";

interface Props {
  devices: DeviceInfo[];
  plc: PLCState | null;
  robot: RobotState | null;
  storage: StorageSlot[];
  activeMission?: IntralogisticsMission | null;
  stationOp?: StationOperation | null;
  cameraActive?: boolean;
}

export function IntralogisticsPanel({
  devices,
  plc,
  robot,
  storage,
  activeMission,
  stationOp,
  cameraActive = false,
}: Props) {
  const [isConfigModalOpen, setConfigModalOpen] = useState(false);
  const [camStreaming, setCamStreaming] = useState(cameraActive);
  const [testQrCode, setTestQrCode] = useState("PROD-TEST-1001");
  const [logs, setLogs] = useState<DeviceCommandLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // Fetch latest device command logs
  const fetchLogs = async () => {
    try {
      const res = await getDeviceLogs(25);
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch {
      // Ignore poll errors
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleStartCamera = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await startDeviceCamera();
      if (res.ok) {
        setCamStreaming(true);
        setMsg("📷 Đã bật luồng Camera thành công");
      } else {
        setMsg("❌ Lỗi khi bật Camera");
      }
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleStopCamera = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await stopDeviceCamera();
      if (res.ok) {
        setCamStreaming(false);
        setMsg("🛑 Đã tắt luồng Camera");
      } else {
        setMsg("❌ Lỗi khi tắt Camera");
      }
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTestQrScan = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await testDeviceCameraQr(testQrCode);
      if (res.ok) {
        const data = await res.json();
        setMsg(`✅ Test QR Scan result: ${JSON.stringify(data.result?.message || data)}`);
        fetchLogs();
      } else {
        setMsg("❌ Lỗi khi thực hiện Test QR Scan");
      }
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleStartDelivery = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await startIntralogisticsMission("DRONE_DELIVERY", "SP001");
      if (res.ok) {
        setMsg("🚀 Đã kích hoạt Nhiệm vụ Xuất kho (DRONE_DELIVERY) thành công");
      } else {
        setMsg("❌ Thất bại khi kích hoạt Nhiệm vụ Xuất kho");
      }
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleStartPickup = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await startIntralogisticsMission("DRONE_PICKUP", "SP002");
      if (res.ok) {
        setMsg("📥 Đã kích hoạt Nhiệm vụ Nhập kho (DRONE_PICKUP) thành công");
      } else {
        setMsg("❌ Thất bại khi kích hoạt Nhiệm vụ Nhập kho");
      }
    } catch (err) {
      setMsg(`Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePauseMission = async () => {
    setLoading(true);
    try {
      const res = await pauseMission();
      if (res.ok) setMsg("⏸️ Đã tạm dừng Nhiệm vụ");
    } catch {
      setMsg("❌ Thất bại khi tạm dừng");
    } finally {
      setLoading(false);
    }
  };

  const handleResumeMission = async () => {
    setLoading(true);
    try {
      const res = await resumeMission();
      if (res.ok) setMsg("▶️ Đã tiếp tục Nhiệm vụ");
    } catch {
      setMsg("❌ Thất bại khi tiếp tục");
    } finally {
      setLoading(false);
    }
  };

  const handleAutoStartQueue = async () => {
    setLoading(true);
    try {
      const res = await triggerAutoStartMissions();
      if (res.ok) {
        const data = await res.json();
        setMsg(data.message);
      }
    } catch {
      setMsg("❌ Lỗi khi kích hoạt chạy tự động");
    } finally {
      setLoading(false);
    }
  };

  const currentPhase = activeMission?.current_phase || "WAITING";
  const missionType = activeMission?.mission_type || "NONE";

  return (
    <div className="intralogistics-container">
      {/* Decoupled 4-Layer Architecture System Banner */}
      <div className="panel fsm-banner" style={{ borderLeft: "4px solid #00F0FF" }}>
        <div className="panel-header-inline">
          <h3>🏛️ ĐIỀU PHỐI KHO THÔNG MINH — KIẾN TRÚC 4 TẦNG DECOUPLED</h3>
          <span className="badge online animate-pulse">
            SYSTEM 4-LAYER ACTIVE
          </span>
        </div>
        <p style={{ margin: "4px 0 0 0", color: "#94a3b8", fontSize: "0.85rem" }}>
          Phân tách độc lập: <b>Layer 1 (Customer Order)</b> ➔ <b>Layer 2 (Mission Lifecycle)</b> ➔ <b>Layer 3 (Station Task)</b> ➔ <b>Layer 4 (PLC & Robot Hardware Drivers)</b>.
        </p>
      </div>

      {/* Layer 1 & Layer 2: Live Mission Orchestration Card */}
      <div className="panel" style={{ borderLeft: "4px solid #8b5cf6", marginTop: "1rem" }}>
        <div className="panel-header-inline">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h3>🚀 Nối Nhiệm Vụ Kho & Đơn Hàng (Layer 1 & 2 Mission Orchestrator)</h3>
            {activeMission && (
              <span className={`status-badge ${activeMission.status === "RUNNING" ? "status-online" : "status-offline"}`}>
                #{activeMission.id} ({activeMission.status})
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button type="button" className="btn btn-primary btn-sm" onClick={handleAutoStartQueue} disabled={loading}>
              ⚡ Chạy Tự Động Hàng Chờ
            </button>
            <button type="button" className="btn btn-success btn-sm" onClick={handleStartDelivery} disabled={loading}>
              📦 Xuất Kho (SP001)
            </button>
            <button type="button" className="btn btn-warning btn-sm" onClick={handleStartPickup} disabled={loading}>
              📥 Nhập Kho (SP002)
            </button>
            {activeMission?.status === "RUNNING" ? (
              <button type="button" className="btn btn-secondary btn-sm" onClick={handlePauseMission} disabled={loading}>
                ⏸️ Tạm Dừng
              </button>
            ) : activeMission?.status === "PAUSED" ? (
              <button type="button" className="btn btn-success btn-sm" onClick={handleResumeMission} disabled={loading}>
                ▶️ Tiếp Tục
              </button>
            ) : null}
          </div>
        </div>

        {activeMission ? (
          <div style={{ marginTop: "12px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "10px", background: "rgba(15, 23, 42, 0.6)", padding: "10px", borderRadius: "6px" }}>
              <div>
                <span style={{ fontSize: "0.75rem", color: "#64748b" }}>NHIỆM VỤ</span>
                <div style={{ fontWeight: "bold", color: "#00F0FF" }}>#{activeMission.id}</div>
              </div>
              <div>
                <span style={{ fontSize: "0.75rem", color: "#64748b" }}>ĐƠN HÀNG (ORDER)</span>
                <div style={{ fontWeight: "bold", color: "#8b5cf6" }}>{activeMission.order_id ? `#${activeMission.order_id}` : "Hệ thống"}</div>
              </div>
              <div>
                <span style={{ fontSize: "0.75rem", color: "#64748b" }}>LOẠI LUỒNG</span>
                <div style={{ fontWeight: "bold", color: missionType === "DRONE_DELIVERY" ? "#10b981" : "#f59e0b" }}>
                  {missionType === "DRONE_DELIVERY" ? "📦 DRONE_DELIVERY (Xuất Kho)" : "📥 DRONE_PICKUP (Nhập Kho)"}
                </div>
              </div>
              <div>
                <span style={{ fontSize: "0.75rem", color: "#64748b" }}>SẢN PHẨM</span>
                <div style={{ fontWeight: "bold", color: "#ffb800" }}>{activeMission.product_id}</div>
              </div>
              <div>
                <span style={{ fontSize: "0.75rem", color: "#64748b" }}>Ô KHO CHỈ ĐỊNH</span>
                <div style={{ fontWeight: "bold", color: "#00F0FF" }}>{activeMission.target_slot || "A1"}</div>
              </div>
            </div>

            {/* Stepper Phase Bar */}
            <div style={{ marginTop: "14px", display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px" }}>
              <div style={{ padding: "8px", borderRadius: "6px", background: currentPhase === "QUEUED" || currentPhase === "WAITING" ? "rgba(0, 240, 255, 0.2)" : "rgba(30, 41, 59, 0.5)", border: currentPhase === "QUEUED" || currentPhase === "WAITING" ? "1px solid #00F0FF" : "1px solid transparent" }}>
                <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>PHASE 1</div>
                <div style={{ fontWeight: "bold", fontSize: "0.85rem", color: "#fff" }}>📋 WAITING (Queued)</div>
              </div>
              <div style={{ padding: "8px", borderRadius: "6px", background: currentPhase === "STATION_PROCESSING" ? "rgba(139, 92, 246, 0.3)" : "rgba(30, 41, 59, 0.5)", border: currentPhase === "STATION_PROCESSING" ? "1px solid #8b5cf6" : "1px solid transparent" }}>
                <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>PHASE 2</div>
                <div style={{ fontWeight: "bold", fontSize: "0.85rem", color: "#fff" }}>⚙️ STATION PROCESSING</div>
              </div>
              <div style={{ padding: "8px", borderRadius: "6px", background: currentPhase === "DRONE_EN_ROUTE" ? "rgba(16, 185, 129, 0.3)" : "rgba(30, 41, 59, 0.5)", border: currentPhase === "DRONE_EN_ROUTE" ? "1px solid #10b981" : "1px solid transparent" }}>
                <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>PHASE 3</div>
                <div style={{ fontWeight: "bold", fontSize: "0.85rem", color: "#fff" }}>🚁 DRONE EN ROUTE</div>
              </div>
              <div style={{ padding: "8px", borderRadius: "6px", background: currentPhase === "COMPLETED" ? "rgba(16, 185, 129, 0.4)" : "rgba(30, 41, 59, 0.5)", border: currentPhase === "COMPLETED" ? "1px solid #10b981" : "1px solid transparent" }}>
                <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>PHASE 4</div>
                <div style={{ fontWeight: "bold", fontSize: "0.85rem", color: "#fff" }}>✅ COMPLETED</div>
              </div>
            </div>

            <div style={{ marginTop: "10px", fontSize: "0.85rem", color: "#cbd5e1", fontStyle: "italic" }}>
              {activeMission.step_details}
            </div>
          </div>
        ) : (
          <div style={{ padding: "12px", textAlign: "center", color: "#64748b", fontSize: "0.9rem" }}>
            Không có nhiệm vụ nào đang hoạt động. Nhấn <b>"⚡ Chạy Tự Động Hàng Chờ"</b> hoặc chọn <b>Xuất/Nhập Kho</b> để bắt đầu.
          </div>
        )}
      </div>

      {/* Layer 3: Station Operation Controller Card */}
      <div className="panel" style={{ borderLeft: "4px solid #10b981", marginTop: "1rem" }}>
        <div className="panel-header-inline">
          <h3>⚙️ Tác Vụ Phần Cứng Trạm Kho (Layer 3 Station Controller)</h3>
          <span className={`status-badge ${stationOp?.status === "RUNNING" ? "status-online" : "status-idle"}`}>
            {stationOp?.operation || "IDLE"} ({stationOp?.status || "READY"})
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "12px", marginTop: "10px", background: "rgba(15, 23, 42, 0.6)", padding: "12px", borderRadius: "6px" }}>
          <div>
            <span style={{ fontSize: "0.75rem", color: "#64748b" }}>LỆNH PHẦN CỨNG ĐANG CHẠY</span>
            <div style={{ fontWeight: "bold", fontSize: "1rem", color: "#00F0FF", marginTop: "2px" }}>
              {stationOp?.current_action || "READY"}
            </div>
          </div>
          <div>
            <span style={{ fontSize: "0.75rem", color: "#64748b" }}>THÔNG BÁO THỰC THI THỜI GIAN THỰC</span>
            <div style={{ color: "#e2e8f0", fontSize: "0.9rem", marginTop: "2px" }}>
              {stationOp?.message || "Trạm Docking Kho đang ở trạng thái sẵn sàng."}
            </div>
          </div>
        </div>
      </div>

      {/* LAN Network Devices Status Bar */}
      <DeviceStatusPanel devices={devices} onOpenConfig={() => setConfigModalOpen(true)} />

      {/* Hardware Connection & Socket Testing Modal */}
      <DeviceConfigModal
        isOpen={isConfigModalOpen}
        onClose={() => setConfigModalOpen(false)}
        devices={devices}
      />

      {/* Main 2-Column Device Controls Grid */}
      <div className="intralogistics-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "1rem" }}>
        {/* PLC Control Card */}
        <PlcControlPanel plc={plc} />

        {/* Robot Control Card */}
        <RobotControlPanel robot={robot} />
      </div>

      {/* Camera Control Card & Storage Grid */}
      <div className="intralogistics-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "1rem" }}>
        {/* Camera Control Card */}
        <div className="panel">
          <div className="panel-header-inline">
            <h3>📷 Quét mã QR Sản phẩm Kho (CAM01)</h3>
            <span className={`status-badge ${camStreaming ? "status-online" : "status-offline"}`}>
              {camStreaming ? "USB CAM ACTIVE" : "USB CAM STOPPED"}
            </span>
          </div>

          {/* Camera Preview Container */}
          <div className="camera-preview-box" style={{ background: "#060911", border: "1px dashed rgba(0, 240, 255, 0.3)", borderRadius: "6px", height: "220px", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", position: "relative" }}>
            {camStreaming ? (
              <img
                src={`${API_BASE}/api/inventory/camera-stream`}
                alt="USB Camera QR Stream"
                style={{ width: "100%", height: "100%", objectFit: "contain" }}
                onError={() => setCamStreaming(false)}
              />
            ) : (
              <div style={{ textAlign: "center", color: "#64748b" }}>
                <span style={{ fontSize: "2rem" }}>📷</span>
                <p style={{ margin: "4px 0 0 0" }}>USB Camera đang tắt (OFF)</p>
              </div>
            )}
          </div>

          {/* Camera Controls */}
          <div className="camera-actions mt-2">
            <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleStartCamera}
                disabled={loading || camStreaming}
              >
                📷 Test USB Camera (Start)
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleStopCamera}
                disabled={loading || !camStreaming}
              >
                ⏹️ Tắt USB Camera (Stop)
              </button>
            </div>

            {/* QR Scan Manual Test Form */}
            <div className="form-group-inline" style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <input
                type="text"
                className="form-control"
                placeholder="Nhập mã QR để test scan..."
                value={testQrCode}
                onChange={(e) => setTestQrCode(e.target.value)}
                style={{ flex: 1 }}
              />
              <button
                type="button"
                className="btn btn-success"
                onClick={handleTestQrScan}
                disabled={loading}
              >
                🔍 Test QR Scan
              </button>
            </div>
          </div>
        </div>

        {/* Warehouse Storage Grid (3x3 A1..C3) */}
        <StorageSlotsGrid slots={storage} />
      </div>

      {/* Device Command History / Log Table */}
      <div className="panel command-log-panel" style={{ marginTop: "1rem" }}>
        <div className="panel-header-inline">
          <h3>📜 Nhật ký Lệnh Thiết bị (Device Command Logs)</h3>
          <button type="button" className="btn btn-outline btn-sm" onClick={fetchLogs}>
            🔄 Làm mới
          </button>
        </div>

        <div className="table-responsive" style={{ maxHeight: "240px", overflowY: "auto", marginTop: "8px" }}>
          <table className="data-table" style={{ width: "100%", fontSize: "0.85rem", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "rgba(15, 23, 42, 0.8)", textAlign: "left" }}>
                <th style={{ padding: "6px 10px" }}>ID</th>
                <th style={{ padding: "6px 10px" }}>Thời gian</th>
                <th style={{ padding: "6px 10px" }}>Thiết bị</th>
                <th style={{ padding: "6px 10px" }}>Lệnh (Command)</th>
                <th style={{ padding: "6px 10px" }}>Target</th>
                <th style={{ padding: "6px 10px" }}>Kết quả</th>
                <th style={{ padding: "6px 10px" }}>Chi tiết</th>
              </tr>
            </thead>
            <tbody>
              {logs.length > 0 ? (
                logs.map((log) => (
                  <tr key={log.id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.05)" }}>
                    <td style={{ padding: "6px 10px", color: "#64748b" }}>#{log.id}</td>
                    <td style={{ padding: "6px 10px", color: "#94a3b8" }}>{new Date(log.timestamp).toLocaleTimeString()}</td>
                    <td style={{ padding: "6px 10px", fontWeight: "bold", color: "#00F0FF" }}>{log.device}</td>
                    <td style={{ padding: "6px 10px", fontWeight: "bold" }}>{log.command}</td>
                    <td style={{ padding: "6px 10px", color: "#ffb800" }}>{log.target || "-"}</td>
                    <td style={{ padding: "6px 10px" }}>
                      <span className={`status-badge ${log.result === "SUCCESS" || log.result === "DONE" ? "status-online" : "status-offline"}`}>
                        {log.result}
                      </span>
                    </td>
                    <td style={{ padding: "6px 10px", color: "#cbd5e1" }}>{log.message}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: "16px", color: "#64748b" }}>
                    Chưa có nhật ký lệnh thiết bị.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {msg && (
        <div className="panel-msg mt-2" style={{ padding: "8px 12px", background: "rgba(0, 240, 255, 0.1)", border: "1px solid #00F0FF", borderRadius: "4px" }}>
          {msg}
        </div>
      )}
    </div>
  );
}
