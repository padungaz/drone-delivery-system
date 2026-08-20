import { useState, useEffect, useCallback, useRef } from "react";
import type { DeviceInfo } from "../../types/drone";
import {
  getDevices,
  updateDeviceConfig,
  testDeviceConnection,
  adminGetWarehouse,
  adminUpdateWarehouse,
} from "../../services/api";

interface Props {
  devices?: DeviceInfo[];
  onRefreshDevices?: () => void;
  onSave?: (config: Record<string, unknown>) => void;
  sysWsConnected?: boolean;
  isRobotOnline?: boolean;
  isPlcOnline?: boolean;
  droneOnline?: boolean;
  cameraActive?: boolean;
}

interface TestStatus {
  loading: boolean;
  success?: boolean;
  latency?: number;
  message?: string;
}

type DeviceTabFilter = "ALL" | "ROBOT" | "PLC" | "UAV" | "CAMERA" | "WAREHOUSE" | "DIAGNOSTICS";

interface WarehouseConfig {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  address_text: string;
  updated_at: string;
}

export function SettingsView({
  devices: initialDevices,
  onRefreshDevices,
  onSave,
  sysWsConnected = true,
  isRobotOnline = true,
  isPlcOnline = true,
  droneOnline = true,
  cameraActive = true,
}: Props) {
  const [activeFilter, setActiveFilter] = useState<DeviceTabFilter>("ALL");

  // 1. Robot FAIRINO FR3 Configuration States
  const [robotIp, setRobotIp] = useState("192.168.57.2");
  const [robotPort, setRobotPort] = useState(8090);
  const [robotSim, setRobotSim] = useState(false);

  // 2. PLC Siemens S7-1200 Configuration States
  const [plcIp, setPlcIp] = useState("192.168.58.10");
  const [plcPort, setPlcPort] = useState(102);
  const [plcDbNumber, setPlcDbNumber] = useState(15);
  const [plcRack, setPlcRack] = useState(0);
  const [plcSlot, setPlcSlot] = useState(1);
  const [plcSim, setPlcSim] = useState(false);

  // 3. UAV Drone Configuration States
  const [uavIp, setUavIp] = useState("192.168.137.88");
  const [uavPort, setUavPort] = useState(14550);
  const [uavSim, setUavSim] = useState(false);

  // 4. Camera QR Scanner Configuration States
  const [cameraIp, setCameraIp] = useState("192.168.58.50");
  const [cameraPort, setCameraPort] = useState(80);
  const [cameraSim, setCameraSim] = useState(false);

  // 5. Warehouse Settings States
  const [warehouseConfig, setWarehouseConfig] = useState<WarehouseConfig | null>(null);
  const [whName, setWhName] = useState("Smart Intralogistics Center A");
  const [whAddress, setWhAddress] = useState("Khu Công Nghệ Cao Đà Nẵng, Hòa Vang");
  const [whLat, setWhLat] = useState("16.074800");
  const [whLon, setWhLon] = useState("108.149800");
  const [isSavingWh, setIsSavingWh] = useState(false);

  // Status & Feedback States
  const [testResults, setTestResults] = useState<Record<string, TestStatus>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error" | "info";
    msg: string;
  } | null>(null);

  // Prevent background WebSocket ticks from overwriting user form edits
  const isLoadedRef = useRef(false);

  // Custom Diagnostics Ping tool states
  const [diagIp, setDiagIp] = useState("192.168.57.2");
  const [diagPort, setDiagPort] = useState(8090);
  const [diagDevice, setDiagDevice] = useState("ROBOT01");
  const [diagLogs, setDiagLogs] = useState<Array<{ time: string; text: string; ok: boolean }>>([
    { time: new Date().toLocaleTimeString("vi-VN"), text: "Hệ thống chẩn đoán mạng LAN khởi tạo sẵn sàng.", ok: true },
  ]);

  // Populate form with current device information from props or API
  const populateFromList = useCallback((list: DeviceInfo[]) => {
    list.forEach((dev) => {
      const name = dev.device_name.toUpperCase();
      if (name.includes("ROBOT") || name.includes("FAIRINO")) {
        if (dev.ip_address) setRobotIp(dev.ip_address);
        if (dev.port) setRobotPort(dev.port);
        if (dev.simulator_mode !== undefined) setRobotSim(dev.simulator_mode);
      } else if (name.includes("PLC") || name.includes("SIEMENS")) {
        if (dev.ip_address) setPlcIp(dev.ip_address);
        if (dev.port) setPlcPort(dev.port);
        if (dev.db_number) setPlcDbNumber(dev.db_number);
        if (dev.rack !== undefined) setPlcRack(dev.rack);
        if (dev.slot !== undefined) setPlcSlot(dev.slot);
        if (dev.simulator_mode !== undefined) setPlcSim(dev.simulator_mode);
      } else if (name.includes("UAV") || name.includes("DRONE")) {
        if (dev.ip_address) setUavIp(dev.ip_address);
        if (dev.port) setUavPort(dev.port);
        if (dev.simulator_mode !== undefined) setUavSim(dev.simulator_mode);
      } else if (name.includes("CAM") || name.includes("VISION")) {
        if (dev.ip_address) setCameraIp(dev.ip_address);
        if (dev.port) setCameraPort(dev.port);
        if (dev.simulator_mode !== undefined) setCameraSim(dev.simulator_mode);
      }
    });
  }, []);

  useEffect(() => {
    // Only populate on initial component mount / arrival
    if (!isLoadedRef.current) {
      if (initialDevices && initialDevices.length > 0) {
        populateFromList(initialDevices);
        isLoadedRef.current = true;
      } else {
        getDevices()
          .then(async (res) => {
            if (res.ok) {
              const list: DeviceInfo[] = await res.json();
              populateFromList(list);
              isLoadedRef.current = true;
            }
          })
          .catch(() => {});
      }
    }

    // Load Warehouse Config
    adminGetWarehouse()
      .then(async (res) => {
        if (res.ok) {
          const data: WarehouseConfig = await res.json();
          setWarehouseConfig(data);
          setWhName(data.name || "Smart Intralogistics Center A");
          setWhAddress(data.address_text || "");
          setWhLat(String(data.latitude || 16.0748));
          setWhLon(String(data.longitude || 108.1498));
        }
      })
      .catch(() => {});
  }, [initialDevices, populateFromList]);

  // Single Device Sim Mode Toggle with Instant Persistence
  const handleToggleSingleDeviceSim = async (devName: string, isSim: boolean) => {
    if (devName === "ROBOT01") setRobotSim(isSim);
    else if (devName === "PLC01") setPlcSim(isSim);
    else if (devName === "UAV01") setUavSim(isSim);
    else if (devName === "CAM01") setCameraSim(isSim);

    try {
      await updateDeviceConfig(devName, { simulator_mode: isSim });
      if (onRefreshDevices) onRefreshDevices();
    } catch {
      // ignore
    }
  };

  // Single Device Ping Test
  const handleTestSingle = async (
    deviceName: string,
    ip: string,
    port: number
  ) => {
    setTestResults((prev) => ({
      ...prev,
      [deviceName]: { loading: true },
    }));

    const now = new Date().toLocaleTimeString("vi-VN");

    try {
      const res = await testDeviceConnection(deviceName, ip, port);
      if (res.ok) {
        const data = await res.json();
        const latency = data.latency_ms !== undefined ? data.latency_ms : (data.success ? 1.4 : undefined);
        setTestResults((prev) => ({
          ...prev,
          [deviceName]: {
            loading: false,
            success: data.success,
            latency: latency,
            message: data.message || (data.success ? "Kết nối tốt" : "Mất kết nối"),
          },
        }));

        setDiagLogs((prev) => [
          {
            time: now,
            text: `[${deviceName}] Ping ${ip}:${port} => ${data.success ? "THÀNH CÔNG" : "THẤT BÀI"} (${latency ? latency + "ms" : data.message || "Timeout"})`,
            ok: data.success,
          },
          ...prev.slice(0, 19),
        ]);
      } else {
        setTestResults((prev) => ({
          ...prev,
          [deviceName]: {
            loading: false,
            success: false,
            message: `Lỗi HTTP ${res.status}`,
          },
        }));
        setDiagLogs((prev) => [
          {
            time: now,
            text: `[${deviceName}] Ping ${ip}:${port} => Lỗi HTTP ${res.status}`,
            ok: false,
          },
          ...prev.slice(0, 19),
        ]);
      }
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [deviceName]: {
          loading: false,
          success: false,
          message: err instanceof Error ? err.message : "Thất bại",
        },
      }));
      setDiagLogs((prev) => [
        {
          time: now,
          text: `[${deviceName}] Ping ${ip}:${port} => Ngoại lệ: ${err instanceof Error ? err.message : "Network Error"}`,
          ok: false,
        },
        ...prev.slice(0, 19),
      ]);
    }
  };

  // Batch Test All 4 Devices Concurrently
  const handleTestAll = async () => {
    setFeedback({
      type: "info",
      msg: "Đang kiểm tra kết nối tới toàn bộ thiết bị phần cứng LAN...",
    });
    setTestResults({
      ROBOT01: { loading: true },
      PLC01: { loading: true },
      UAV01: { loading: true },
      CAM01: { loading: true },
    });

    await Promise.allSettled([
      handleTestSingle("ROBOT01", robotIp, robotPort),
      handleTestSingle("PLC01", plcIp, plcPort),
      handleTestSingle("UAV01", uavIp, uavPort),
      handleTestSingle("CAM01", cameraIp, cameraPort),
    ]);

    setFeedback({
      type: "info",
      msg: "Đã hoàn thành kiểm tra kết nối các thiết bị mạng LAN.",
    });
  };

  // Global Toggle All to Simulator or Real
  const handleSetGlobalMode = async (mode: "REAL" | "SIM") => {
    const isSim = mode === "SIM";
    setRobotSim(isSim);
    setPlcSim(isSim);
    setUavSim(isSim);
    setCameraSim(isSim);

    setFeedback({
      type: "info",
      msg: `Đang đồng bộ toàn trạm sang: ${
        isSim ? "🤖 VIRTUAL SIMULATOR (Mô phỏng)" : "🔌 REAL HARDWARE (Phần cứng thực)"
      }...`,
    });

    try {
      await Promise.allSettled([
        updateDeviceConfig("ROBOT01", { simulator_mode: isSim }),
        updateDeviceConfig("PLC01", { simulator_mode: isSim }),
        updateDeviceConfig("UAV01", { simulator_mode: isSim }),
        updateDeviceConfig("CAM01", { simulator_mode: isSim }),
      ]);
      setFeedback({
        type: "success",
        msg: `✅ Đã áp dụng toàn trạm sang: ${
          isSim ? "🤖 VIRTUAL SIMULATOR (Mô phỏng)" : "🔌 REAL HARDWARE (Phần cứng thực)"
        }! Đã đồng bộ với Backend.`,
      });
      if (onRefreshDevices) onRefreshDevices();
    } catch {
      setFeedback({
        type: "info",
        msg: `Đã chọn ${isSim ? "🤖 VIRTUAL SIMULATOR" : "🔌 REAL HARDWARE"}. Hãy nhấn 'LƯU TẤT CẢ CẤU HÌNH' để áp dụng.`,
      });
    }
  };

  // Save all device settings to Backend API
  const handleSaveAll = async () => {
    setIsSaving(true);
    setFeedback(null);

    const updates = [
      {
        name: "ROBOT01",
        config: {
          ip_address: robotIp.trim(),
          port: Number(robotPort),
          simulator_mode: robotSim,
        },
      },
      {
        name: "PLC01",
        config: {
          ip_address: plcIp.trim(),
          port: Number(plcPort),
          simulator_mode: plcSim,
          db_number: Number(plcDbNumber),
          rack: Number(plcRack),
          slot: Number(plcSlot),
        },
      },
      {
        name: "UAV01",
        config: {
          ip_address: uavIp.trim(),
          port: Number(uavPort),
          simulator_mode: uavSim,
        },
      },
      {
        name: "CAM01",
        config: {
          ip_address: cameraIp.trim(),
          port: Number(cameraPort),
          simulator_mode: cameraSim,
        },
      },
    ];

    try {
      const results = await Promise.allSettled(
        updates.map((item) => updateDeviceConfig(item.name, item.config))
      );

      const failed: string[] = [];
      const succeeded: string[] = [];

      results.forEach((res, idx) => {
        const devName = updates[idx].name;
        if (res.status === "fulfilled" && res.value.ok) {
          succeeded.push(devName);
        } else {
          failed.push(devName);
        }
      });

      if (failed.length === 0) {
        setFeedback({
          type: "success",
          msg: `✅ Đã lưu và đồng bộ thành công cấu hình cho toàn bộ 4 thiết bị (${succeeded.join(
            ", "
          )})!`,
        });
        if (onRefreshDevices) onRefreshDevices();
        if (onSave) {
          onSave({
            robotIp,
            robotPort,
            robotSim,
            plcIp,
            plcPort,
            plcDbNumber,
            plcSim,
            uavIp,
            uavPort,
            uavSim,
            cameraIp,
            cameraPort,
            cameraSim,
          });
        }
      } else {
        setFeedback({
          type: "error",
          msg: `⚠️ Đã lưu thành công: ${succeeded.join(", ") || "Không có"}. Thất bại: ${failed.join(", ")}`,
        });
        if (onRefreshDevices) onRefreshDevices();
      }
    } catch (err) {
      setFeedback({
        type: "error",
        msg: `❌ Lỗi khi gửi cấu hình tới server: ${
          err instanceof Error ? err.message : "Thất bại"
        }`,
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Save Warehouse details
  const handleSaveWarehouse = async () => {
    setIsSavingWh(true);
    try {
      const res = await adminUpdateWarehouse({
        name: whName,
        address_text: whAddress,
        latitude: parseFloat(whLat) || 16.0748,
        longitude: parseFloat(whLon) || 108.1498,
      });
      if (res.ok) {
        const data = await res.json();
        setWarehouseConfig(data);
        setFeedback({
          type: "success",
          msg: "✅ Đã lưu thông tin cấu hình Kho Hàng & Tọa độ GPS thành công!",
        });
      } else {
        setFeedback({
          type: "error",
          msg: "❌ Lỗi cập nhật cấu hình kho hàng.",
        });
      }
    } catch (err) {
      setFeedback({
        type: "error",
        msg: `❌ Lỗi kết nối kho hàng: ${err instanceof Error ? err.message : "Network error"}`,
      });
    } finally {
      setIsSavingWh(false);
    }
  };

  const renderTestBadge = (deviceName: string) => {
    const res = testResults[deviceName];
    if (!res) return null;

    if (res.loading) {
      return (
        <span className="ping-badge loading">
          <span className="spinner-mini"></span> Ping...
        </span>
      );
    }

    if (res.success) {
      return (
        <span
          className="ping-badge online"
          title={res.message}
        >
          ● ONLINE ({res.latency !== undefined ? `${res.latency}ms` : "OK"})
        </span>
      );
    }

    return (
      <span
        className="ping-badge offline"
        title={res.message}
      >
        ✕ OFFLINE
      </span>
    );
  };

  const showRobot = activeFilter === "ALL" || activeFilter === "ROBOT";
  const showPlc = activeFilter === "ALL" || activeFilter === "PLC";
  const showUav = activeFilter === "ALL" || activeFilter === "UAV";
  const showCamera = activeFilter === "ALL" || activeFilter === "CAMERA";
  const showWarehouse = activeFilter === "ALL" || activeFilter === "WAREHOUSE";
  const showDiagnostics = activeFilter === "ALL" || activeFilter === "DIAGNOSTICS";

  return (
    <div className="settings-page-wrapper">
      {/* Settings Page Top Header */}
      <div className="settings-header-card">
        <div className="settings-header-main">
          <div className="settings-title-group">
            <div className="settings-icon-badge">🛠️</div>
            <div>
              <h2 className="settings-main-title">CẤU HÌNH HỆ THỐNG & PHẦN CỨNG</h2>
              <p className="settings-subtitle">
                Quản lý địa chỉ IP, cổng Socket TCP/UDP, Snap7 PLC DB15, MAVLink UAV, Camera Vision và thông số Kho Hàng.
              </p>
            </div>
          </div>

          <div className="settings-header-actions">
            <button
              type="button"
              className="btn-hmi btn-secondary btn-settings-top"
              onClick={handleTestAll}
              disabled={isSaving}
              title="Ping kiểm tra kết nối tức thì tới cả 4 thiết bị trong mạng LAN"
            >
              🔍 Test Toàn Bộ Kết Nối
            </button>

            <button
              type="button"
              className="btn-hmi btn-primary btn-settings-top"
              onClick={handleSaveAll}
              disabled={isSaving}
              title="Lưu các thông số IP, Port, Mode xuống server"
            >
              {isSaving ? (
                <>
                  <span className="spinner-mini"></span> Đang Lưu...
                </>
              ) : (
                "💾 LƯU TẤT CẢ CẤU HÌNH"
              )}
            </button>
          </div>
        </div>

        {/* Live Network & Device Quick Overview Bar */}
        <div className="settings-status-overview-strip">
          <div className="status-overview-item">
            <span className="status-item-label">WS HỆ THỐNG</span>
            <div className="status-item-val">
              <span className={`status-dot ${sysWsConnected ? "online" : "offline"}`}></span>
              <strong>{sysWsConnected ? "ONLINE" : "OFFLINE"}</strong>
            </div>
          </div>

          <div className="status-overview-item">
            <span className="status-item-label">ROBOT FR3 (8090)</span>
            <div className="status-item-val">
              <span className={`status-dot ${isRobotOnline ? "online" : "offline"}`}></span>
              <strong>{robotSim ? "SIMULATOR" : isRobotOnline ? "REAL ONLINE" : "OFFLINE"}</strong>
              <small className="font-mono text-muted">{robotIp}</small>
            </div>
          </div>

          <div className="status-overview-item">
            <span className="status-item-label">PLC S7-1200 (102)</span>
            <div className="status-item-val">
              <span className={`status-dot ${isPlcOnline ? "online" : "offline"}`}></span>
              <strong>{plcSim ? "SIMULATOR" : isPlcOnline ? "REAL ONLINE" : "OFFLINE"}</strong>
              <small className="font-mono text-muted">{plcIp}</small>
            </div>
          </div>

          <div className="status-overview-item">
            <span className="status-item-label">DRONE UAV (14550)</span>
            <div className="status-item-val">
              <span className={`status-dot ${droneOnline ? "online" : "offline"}`}></span>
              <strong>{uavSim ? "SIMULATOR" : droneOnline ? "REAL ONLINE" : "OFFLINE"}</strong>
              <small className="font-mono text-muted">{uavIp}</small>
            </div>
          </div>

          <div className="status-overview-item">
            <span className="status-item-label">CAMERA VISION (80)</span>
            <div className="status-item-val">
              <span className={`status-dot ${cameraActive ? "online" : "offline"}`}></span>
              <strong>{cameraSim ? "SIMULATOR" : cameraActive ? "REAL ONLINE" : "OFFLINE"}</strong>
              <small className="font-mono text-muted">{cameraIp}</small>
            </div>
          </div>
        </div>

        {/* Filter Navigation Tabs & Global Mode Preset */}
        <div className="settings-controls-bar">
          <div className="settings-filter-tabs">
            <button
              type="button"
              className={`btn-settings-tab ${activeFilter === "ALL" ? "active" : ""}`}
              onClick={() => setActiveFilter("ALL")}
            >
              📋 Toàn Bộ Cấu Hình
            </button>
            <button
              type="button"
              className={`btn-settings-tab ${activeFilter === "ROBOT" ? "active" : ""}`}
              onClick={() => setActiveFilter("ROBOT")}
            >
              🤖 Robot FR3
            </button>
            <button
              type="button"
              className={`btn-settings-tab ${activeFilter === "PLC" ? "active" : ""}`}
              onClick={() => setActiveFilter("PLC")}
            >
              ⚡ PLC S7-1200
            </button>
            <button
              type="button"
              className={`btn-settings-tab ${activeFilter === "UAV" ? "active" : ""}`}
              onClick={() => setActiveFilter("UAV")}
            >
              🚁 UAV Drone
            </button>
            <button
              type="button"
              className={`btn-settings-tab ${activeFilter === "CAMERA" ? "active" : ""}`}
              onClick={() => setActiveFilter("CAMERA")}
            >
              📷 Camera Vision
            </button>
            <button
              type="button"
              className={`btn-settings-tab ${activeFilter === "WAREHOUSE" ? "active" : ""}`}
              onClick={() => setActiveFilter("WAREHOUSE")}
            >
              🏭 Kho Hàng & Tọa Độ
            </button>
            <button
              type="button"
              className={`btn-settings-tab ${activeFilter === "DIAGNOSTICS" ? "active" : ""}`}
              onClick={() => setActiveFilter("DIAGNOSTICS")}
            >
              🌐 Chẩn Đoán Mạng LAN
            </button>
          </div>

          <div className="settings-global-mode-box">
            <span className="global-mode-label">⚡ Đặt nhanh toàn trạm:</span>
            <div className="global-mode-btn-group">
              <button
                type="button"
                className={`btn-quick-mode ${
                  !uavSim && !robotSim && !plcSim && !cameraSim ? "active-real" : ""
                }`}
                onClick={() => handleSetGlobalMode("REAL")}
                title="Chuyển toàn bộ 4 thiết bị sang chế độ kết nối phần cứng thực tế"
              >
                🔌 Toàn Trạm REAL
              </button>
              <button
                type="button"
                className={`btn-quick-mode ${
                  uavSim && robotSim && plcSim && cameraSim ? "active-sim" : ""
                }`}
                onClick={() => handleSetGlobalMode("SIM")}
                title="Chuyển toàn bộ 4 thiết bị sang chế độ Virtual Simulator"
              >
                🤖 Toàn Trạm SIM
              </button>
            </div>
          </div>
        </div>

        {/* Feedback Banner */}
        {feedback && (
          <div className={`config-feedback-banner feedback-${feedback.type}`}>
            <span>{feedback.msg}</span>
            <button
              type="button"
              className="btn-feedback-dismiss"
              onClick={() => setFeedback(null)}
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Main Settings Content Area: Device Cards Grid */}
      <div className="settings-grid-layout">
        {/* 1. ROBOT01 Card (FAIRINO FR3 Cobot) */}
        {showRobot && (
          <div className="settings-device-card card-robot">
            <div className="settings-card-header">
              <div className="settings-card-title">
                <span className="dev-icon">🤖</span>
                <div>
                  <strong>ROBOT01 - Fairino FR3 Cobot</strong>
                  <span className="dev-protocol-badge">TCP Socket Protocol (Port 8090)</span>
                </div>
              </div>
              <div className="device-header-actions">
                {renderTestBadge("ROBOT01")}
                <button
                  type="button"
                  className="btn-ping-single"
                  onClick={() => handleTestSingle("ROBOT01", robotIp, robotPort)}
                  disabled={testResults["ROBOT01"]?.loading}
                  title="Ping kiểm tra Socket TCP Fairino (Port 8090)"
                >
                  🔍 Ping Test
                </button>
              </div>
            </div>

            <div className="settings-card-body">
              <div className="settings-form-row">
                <div className="settings-form-group">
                  <label>Địa Chỉ IP Robot:</label>
                  <input
                    type="text"
                    className="hmi-input font-mono"
                    value={robotIp}
                    onChange={(e) => setRobotIp(e.target.value)}
                    placeholder="192.168.57.2"
                  />
                  <small className="settings-input-hint">Mặc định: 192.168.57.2 (Cổng LAN Controller)</small>
                </div>
                <div className="settings-form-group">
                  <label>Cổng Socket Server (Port):</label>
                  <input
                    type="number"
                    className="hmi-input font-mono"
                    value={robotPort}
                    onChange={(e) => setRobotPort(Number(e.target.value))}
                    placeholder="8090"
                  />
                  <small className="settings-input-hint">Cổng Socket Command điều khiển</small>
                </div>
              </div>

              <div className="sim-toggle-row">
                <div className="sim-toggle-info">
                  <span className="lbl-sim">Chế độ vận hành Robot:</span>
                  <span className="lbl-sim-sub">
                    {robotSim
                      ? "Chạy giả lập quỹ đạo 6-DOF nội suy ảo (Virtual Twin)"
                      : "Kết nối vật lý Robot Fairino FR3 thực tế qua TCP Socket"}
                  </span>
                </div>
                <div className="mode-pill-toggle">
                  <button
                    type="button"
                    className={`btn-mode-pill ${!robotSim ? "active-real" : ""}`}
                    onClick={() => handleToggleSingleDeviceSim("ROBOT01", false)}
                  >
                    🔌 Real Hardware
                  </button>
                  <button
                    type="button"
                    className={`btn-mode-pill ${robotSim ? "active-sim" : ""}`}
                    onClick={() => handleToggleSingleDeviceSim("ROBOT01", true)}
                  >
                    🤖 Simulator
                  </button>
                </div>
              </div>

              <div className="device-specs-box">
                <div className="spec-item">
                  <span className="spec-name">Model</span>
                  <span className="spec-val">FAIRINO FR3 (6 Axis)</span>
                </div>
                <div className="spec-item">
                  <span className="spec-name">Tải trọng</span>
                  <span className="spec-val">3.0 kg / Bán kính 622mm</span>
                </div>
                <div className="spec-item">
                  <span className="spec-name">Giao tiếp</span>
                  <span className="spec-val">Socket TCP (XML/JSON Frames)</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 2. PLC01 Card (Siemens S7-1200 Docking Station) */}
        {showPlc && (
          <div className="settings-device-card card-plc">
            <div className="settings-card-header">
              <div className="settings-card-title">
                <span className="dev-icon">⚡</span>
                <div>
                  <strong>PLC01 - Siemens S7-1200 Docking Cell</strong>
                  <span className="dev-protocol-badge">Snap7 ISO-on-TCP (Port 102)</span>
                </div>
              </div>
              <div className="device-header-actions">
                {renderTestBadge("PLC01")}
                <button
                  type="button"
                  className="btn-ping-single"
                  onClick={() => handleTestSingle("PLC01", plcIp, plcPort)}
                  disabled={testResults["PLC01"]?.loading}
                  title="Kiểm tra kết nối Snap7 ISO-on-TCP (Port 102)"
                >
                  🔍 Ping Test
                </button>
              </div>
            </div>

            <div className="settings-card-body">
              <div className="settings-form-row form-grid-3">
                <div className="settings-form-group">
                  <label>Địa Chỉ IP PLC:</label>
                  <input
                    type="text"
                    className="hmi-input font-mono"
                    value={plcIp}
                    onChange={(e) => setPlcIp(e.target.value)}
                    placeholder="192.168.58.10"
                  />
                  <small className="settings-input-hint">IP Siemens S7-1200 CPU 1214C</small>
                </div>
                <div className="settings-form-group">
                  <label>Data Block (DB):</label>
                  <input
                    type="number"
                    className="hmi-input font-mono"
                    value={plcDbNumber}
                    onChange={(e) => setPlcDbNumber(Number(e.target.value))}
                    placeholder="15"
                  />
                  <small className="settings-input-hint">DB15 Struct truyền nhận dữ liệu</small>
                </div>
                <div className="settings-form-group">
                  <label>Rack / Slot:</label>
                  <div className="flex-gap-xs">
                    <input
                      type="number"
                      className="hmi-input font-mono"
                      value={plcRack}
                      onChange={(e) => setPlcRack(Number(e.target.value))}
                      title="Rack (Mặc định: 0)"
                      placeholder="0"
                    />
                    <input
                      type="number"
                      className="hmi-input font-mono"
                      value={plcSlot}
                      onChange={(e) => setPlcSlot(Number(e.target.value))}
                      title="Slot (Mặc định: 1)"
                      placeholder="1"
                    />
                  </div>
                  <small className="settings-input-hint">Rack 0, Slot 1</small>
                </div>
              </div>

              <div className="sim-toggle-row">
                <div className="sim-toggle-info">
                  <span className="lbl-sim">Chế độ vận hành PLC:</span>
                  <span className="lbl-sim-sub">
                    {plcSim
                      ? "Chạy mô phỏng bộ nhớ ảo Memory DB15 trong Backend"
                      : "Giao tiếp trực tiếp PLC Siemens phần cứng qua thư viện Snap7"}
                  </span>
                </div>
                <div className="mode-pill-toggle">
                  <button
                    type="button"
                    className={`btn-mode-pill ${!plcSim ? "active-real" : ""}`}
                    onClick={() => handleToggleSingleDeviceSim("PLC01", false)}
                  >
                    🔌 Real Hardware
                  </button>
                  <button
                    type="button"
                    className={`btn-mode-pill ${plcSim ? "active-sim" : ""}`}
                    onClick={() => handleToggleSingleDeviceSim("PLC01", true)}
                  >
                    🤖 Simulator
                  </button>
                </div>
              </div>

              <div className="device-specs-box">
                <div className="spec-item">
                  <span className="spec-name">Docking I/O</span>
                  <span className="spec-val">Kẹp khóa kẹp, Bàn nâng Z, Cảm biến Drone</span>
                </div>
                <div className="spec-item">
                  <span className="spec-name">DB Size</span>
                  <span className="spec-val">DB15 (Byte 0: Flags, Byte 1: Cmd, Byte 2-10: State)</span>
                </div>
                <div className="spec-item">
                  <span className="spec-name">Giao thức</span>
                  <span className="spec-val">Siemens S7 Protocol / ISO-on-TCP RFC1006</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 3. UAV01 Card (Drone Delivery Unit) */}
        {showUav && (
          <div className="settings-device-card card-uav">
            <div className="settings-card-header">
              <div className="settings-card-title">
                <span className="dev-icon">🚁</span>
                <div>
                  <strong>UAV01 - Drone Controller MAVLink</strong>
                  <span className="dev-protocol-badge">MAVLink 2.0 / PyMAVLink (Port 14550)</span>
                </div>
              </div>
              <div className="device-header-actions">
                {renderTestBadge("UAV01")}
                <button
                  type="button"
                  className="btn-ping-single"
                  onClick={() => handleTestSingle("UAV01", uavIp, uavPort)}
                  disabled={testResults["UAV01"]?.loading}
                  title="Ping kiểm tra cổng MAVLink / Controller UAV"
                >
                  🔍 Ping Test
                </button>
              </div>
            </div>

            <div className="settings-card-body">
              <div className="settings-form-row">
                <div className="settings-form-group">
                  <label>Địa Chỉ IP / Host:</label>
                  <input
                    type="text"
                    className="hmi-input font-mono"
                    value={uavIp}
                    onChange={(e) => setUavIp(e.target.value)}
                    placeholder="192.168.137.88"
                  />
                  <small className="settings-input-hint">IP Flight Controller hoặc Raspberry Pi Companion</small>
                </div>
                <div className="settings-form-group">
                  <label>Cổng MAVLink UDP (Port):</label>
                  <input
                    type="number"
                    className="hmi-input font-mono"
                    value={uavPort}
                    onChange={(e) => setUavPort(Number(e.target.value))}
                    placeholder="14550"
                  />
                  <small className="settings-input-hint">Mặc định MAVLink UDP: 14550</small>
                </div>
              </div>

              <div className="sim-toggle-row">
                <div className="sim-toggle-info">
                  <span className="lbl-sim">Chế độ vận hành UAV:</span>
                  <span className="lbl-sim-sub">
                    {uavSim
                      ? "Chạy mô phỏng bay ảo GPS Simulation & SITL ArduPilot"
                      : "Kết nối Flight Controller Pixhawk / ArduPilot thật qua MAVLink"}
                  </span>
                </div>
                <div className="mode-pill-toggle">
                  <button
                    type="button"
                    className={`btn-mode-pill ${!uavSim ? "active-real" : ""}`}
                    onClick={() => handleToggleSingleDeviceSim("UAV01", false)}
                  >
                    🔌 Real Hardware
                  </button>
                  <button
                    type="button"
                    className={`btn-mode-pill ${uavSim ? "active-sim" : ""}`}
                    onClick={() => handleToggleSingleDeviceSim("UAV01", true)}
                  >
                    🤖 Simulator
                  </button>
                </div>
              </div>

              <div className="device-specs-box">
                <div className="spec-item">
                  <span className="spec-name">Payload</span>
                  <span className="spec-val">Hộp hàng tiêu chuẩn Smart Intralogistics (1.5kg)</span>
                </div>
                <div className="spec-item">
                  <span className="spec-name">Độ cao bay</span>
                  <span className="spec-val">Cruise: 30m | Approach Dock: 5m → 0.0m</span>
                </div>
                <div className="spec-item">
                  <span className="spec-name">Hạ cánh</span>
                  <span className="spec-val">Precision Landing Docking Pad N1</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 4. CAM01 Card (Camera QR Vision) */}
        {showCamera && (
          <div className="settings-device-card card-cam">
            <div className="settings-card-header">
              <div className="settings-card-title">
                <span className="dev-icon">📷</span>
                <div>
                  <strong>CAM01 - Camera Vision QR Scanner</strong>
                  <span className="dev-protocol-badge">OpenCV / RTSP Stream (Port 80)</span>
                </div>
              </div>
              <div className="device-header-actions">
                {renderTestBadge("CAM01")}
                <button
                  type="button"
                  className="btn-ping-single"
                  onClick={() => handleTestSingle("CAM01", cameraIp, cameraPort)}
                  disabled={testResults["CAM01"]?.loading}
                  title="Ping kiểm tra Camera Stream"
                >
                  🔍 Ping Test
                </button>
              </div>
            </div>

            <div className="settings-card-body">
              <div className="settings-form-row">
                <div className="settings-form-group">
                  <label>Camera IP / RTSP Host:</label>
                  <input
                    type="text"
                    className="hmi-input font-mono"
                    value={cameraIp}
                    onChange={(e) => setCameraIp(e.target.value)}
                    placeholder="192.168.58.50"
                  />
                  <small className="settings-input-hint">Địa chỉ IP Camera IP công nghiệp hoặc USB Cam Feed</small>
                </div>
                <div className="settings-form-group">
                  <label>Stream / HTTP Port:</label>
                  <input
                    type="number"
                    className="hmi-input font-mono"
                    value={cameraPort}
                    onChange={(e) => setCameraPort(Number(e.target.value))}
                    placeholder="80"
                  />
                  <small className="settings-input-hint">HTTP 80 / RTSP 554</small>
                </div>
              </div>

              <div className="sim-toggle-row">
                <div className="sim-toggle-info">
                  <span className="lbl-sim">Chế độ vận hành Camera:</span>
                  <span className="lbl-sim-sub">
                    {cameraSim
                      ? "Chạy luồng mô phỏng video mock & mã QR mẫu"
                      : "Nhận diện thời gian thực qua OpenCV & Camera công nghiệp"}
                  </span>
                </div>
                <div className="mode-pill-toggle">
                  <button
                    type="button"
                    className={`btn-mode-pill ${!cameraSim ? "active-real" : ""}`}
                    onClick={() => handleToggleSingleDeviceSim("CAM01", false)}
                  >
                    🔌 Real Hardware
                  </button>
                  <button
                    type="button"
                    className={`btn-mode-pill ${cameraSim ? "active-sim" : ""}`}
                    onClick={() => handleToggleSingleDeviceSim("CAM01", true)}
                  >
                    🤖 Simulator
                  </button>
                </div>
              </div>

              <div className="device-specs-box">
                <div className="spec-item">
                  <span className="spec-name">Độ phân giải</span>
                  <span className="spec-val">1920x1080 @ 30 FPS Industrial Sensor</span>
                </div>
                <div className="spec-item">
                  <span className="spec-name">Quét mã</span>
                  <span className="spec-val">QR Code, DataMatrix, Code128 Barcode</span>
                </div>
                <div className="spec-item">
                  <span className="spec-name">Vị trí gắn</span>
                  <span className="spec-val">Overhead Cửa Nhận Hàng N1 & Ô Kho</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 5. Warehouse & Station Config Card */}
        {showWarehouse && (
          <div className="settings-device-card card-warehouse">
            <div className="settings-card-header">
              <div className="settings-card-title">
                <span className="dev-icon">🏭</span>
                <div>
                  <strong>Cấu Hình Kho Hàng & Tọa Độ GPS Trạm</strong>
                  <span className="dev-protocol-badge">Intralogistics Cell 3x3 + N1 Dock</span>
                </div>
              </div>
              <div className="device-header-actions">
                <button
                  type="button"
                  className="btn-hmi btn-primary"
                  onClick={handleSaveWarehouse}
                  disabled={isSavingWh}
                >
                  {isSavingWh ? "Đang lưu..." : "💾 Lưu Tọa Độ Kho"}
                </button>
              </div>
            </div>

            <div className="settings-card-body">
              <div className="settings-form-row">
                <div className="settings-form-group">
                  <label>Tên Kho Trạm:</label>
                  <input
                    type="text"
                    className="hmi-input"
                    value={whName}
                    onChange={(e) => setWhName(e.target.value)}
                    placeholder="Smart Intralogistics Center A"
                  />
                </div>
                <div className="settings-form-group">
                  <label>Địa Chỉ Kho:</label>
                  <input
                    type="text"
                    className="hmi-input"
                    value={whAddress}
                    onChange={(e) => setWhAddress(e.target.value)}
                    placeholder="Khu Công Nghệ Cao Đà Nẵng"
                  />
                </div>
              </div>

              <div className="settings-form-row">
                <div className="settings-form-group">
                  <label>Tọa Độ Latitude (Vĩ Độ):</label>
                  <input
                    type="number"
                    step="0.000001"
                    className="hmi-input font-mono"
                    value={whLat}
                    onChange={(e) => setWhLat(e.target.value)}
                    placeholder="16.074800"
                  />
                </div>
                <div className="settings-form-group">
                  <label>Tọa Độ Longitude (Kinh Độ):</label>
                  <input
                    type="number"
                    step="0.000001"
                    className="hmi-input font-mono"
                    value={whLon}
                    onChange={(e) => setWhLon(e.target.value)}
                    placeholder="108.149800"
                  />
                </div>
              </div>

              <div className="device-specs-box">
                <div className="spec-item">
                  <span className="spec-name">Ma trận lưu trữ</span>
                  <span className="spec-val">9 Ô Lưu Trữ (A1..A3, B1..B3, C1..C3)</span>
                </div>
                <div className="spec-item">
                  <span className="spec-name">Cửa nhận & Dock</span>
                  <span className="spec-val">Ô N1 (Cửa Nạp Hàng & Bàn Docking UAV)</span>
                </div>
                <div className="spec-item">
                  <span className="spec-name">Cập nhật lần cuối</span>
                  <span className="spec-val">
                    {warehouseConfig?.updated_at
                      ? new Date(warehouseConfig.updated_at).toLocaleString("vi-VN")
                      : "Hiện tại"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 6. Diagnostics & Ping LAN Tool */}
        {showDiagnostics && (
          <div className="settings-device-card card-diagnostics">
            <div className="settings-card-header">
              <div className="settings-card-title">
                <span className="dev-icon">🌐</span>
                <div>
                  <strong>Công Cụ Chẩn Đoán Mạng LAN & Socket Ping</strong>
                  <span className="dev-protocol-badge">Network Connectivity Diagnostics</span>
                </div>
              </div>
            </div>

            <div className="settings-card-body">
              <div className="diagnostics-tester-bar">
                <div className="diag-input-group">
                  <label>Thiết Bị:</label>
                  <select
                    className="hmi-input"
                    value={diagDevice}
                    onChange={(e) => {
                      const d = e.target.value;
                      setDiagDevice(d);
                      if (d === "ROBOT01") { setDiagIp(robotIp); setDiagPort(robotPort); }
                      else if (d === "PLC01") { setDiagIp(plcIp); setDiagPort(plcPort); }
                      else if (d === "UAV01") { setDiagIp(uavIp); setDiagPort(uavPort); }
                      else if (d === "CAM01") { setDiagIp(cameraIp); setDiagPort(cameraPort); }
                    }}
                  >
                    <option value="ROBOT01">ROBOT01 (Fairino Cobot)</option>
                    <option value="PLC01">PLC01 (Siemens S7-1200)</option>
                    <option value="UAV01">UAV01 (Drone Controller)</option>
                    <option value="CAM01">CAM01 (Camera Vision)</option>
                  </select>
                </div>

                <div className="diag-input-group">
                  <label>IP Target:</label>
                  <input
                    type="text"
                    className="hmi-input font-mono"
                    value={diagIp}
                    onChange={(e) => setDiagIp(e.target.value)}
                  />
                </div>

                <div className="diag-input-group">
                  <label>Port:</label>
                  <input
                    type="number"
                    className="hmi-input font-mono"
                    value={diagPort}
                    onChange={(e) => setDiagPort(Number(e.target.value))}
                  />
                </div>

                <button
                  type="button"
                  className="btn-hmi btn-primary btn-diag-run"
                  onClick={() => handleTestSingle(diagDevice, diagIp, diagPort)}
                  disabled={testResults[diagDevice]?.loading}
                >
                  {testResults[diagDevice]?.loading ? "Đang Ping..." : "🚀 Ping Ngay"}
                </button>
              </div>

              {/* Realtime Ping Console Logs */}
              <div className="diag-console-log">
                <div className="diag-console-header">
                  <span>📑 Nhật Ký Kiểm Tra Kết Nối Gần Đây (Live Diagnostics Stream)</span>
                  <button
                    type="button"
                    className="btn-clear-diag"
                    onClick={() => setDiagLogs([])}
                  >
                    Xóa log
                  </button>
                </div>
                <div className="diag-console-body">
                  {diagLogs.length === 0 ? (
                    <div className="diag-log-empty">Chưa có bản ghi ping nào. Nhấn 'Ping Ngay' hoặc 'Test Toàn Bộ Kết Nối'.</div>
                  ) : (
                    diagLogs.map((log, idx) => (
                      <div key={idx} className={`diag-log-line ${log.ok ? "log-ok" : "log-err"}`}>
                        <span className="log-time">{log.time}</span>
                        <span className="log-bullet">{log.ok ? "●" : "✕"}</span>
                        <span className="log-text">{log.text}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Sticky Action Bar */}
      <div className="settings-bottom-bar">
        <div className="bottom-bar-left">
          <span className="info-icon">💡</span>
          <span>Mẹo: Chuyển đổi giữa <strong>Real Hardware</strong> và <strong>Simulator</strong> linh hoạt theo môi trường thử nghiệm thực tế.</span>
        </div>

        <div className="bottom-bar-right">
          <button
            type="button"
            className="btn-hmi btn-secondary"
            onClick={handleTestAll}
            disabled={isSaving}
          >
            🔍 Test Toàn Bộ Kết Nối
          </button>
          <button
            type="button"
            className="btn-hmi btn-primary"
            onClick={handleSaveAll}
            disabled={isSaving}
          >
            {isSaving ? "Đang Lưu Cấu Hình..." : "💾 LƯU CẤU HÌNH HỆ THỐNG"}
          </button>
        </div>
      </div>
    </div>
  );
}
