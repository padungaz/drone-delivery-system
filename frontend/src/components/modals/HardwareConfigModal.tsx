import { useState, useEffect } from "react";
import type { DeviceInfo } from "../../types/drone";
import {
  getDevices,
  updateDeviceConfig,
  testDeviceConnection,
} from "../../services/api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  devices?: DeviceInfo[];
  onRefreshDevices?: () => void;
  onSave?: (config: Record<string, unknown>) => void;
}

interface TestStatus {
  loading: boolean;
  success?: boolean;
  latency?: number;
  message?: string;
}

type DeviceTabFilter = "ALL" | "ROBOT" | "PLC" | "UAV" | "CAMERA";

export function HardwareConfigModal({
  isOpen,
  onClose,
  devices: initialDevices,
  onRefreshDevices,
  onSave,
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
  const [cameraIndex, setCameraIndex] = useState(0);
  const [cameraSim, setCameraSim] = useState(false);

  // Status & Feedback States
  const [testResults, setTestResults] = useState<Record<string, TestStatus>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error" | "info";
    msg: string;
  } | null>(null);

  // Populate form with current device information from props or API
  useEffect(() => {
    if (!isOpen) return;

    setFeedback(null);
    setTestResults({});

    const populateFromList = (list: DeviceInfo[]) => {
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
          if (dev.port !== undefined) setCameraIndex(dev.port);
          if (dev.simulator_mode !== undefined) setCameraSim(dev.simulator_mode);
        }
      });
    };

    if (initialDevices && initialDevices.length > 0) {
      populateFromList(initialDevices);
    } else {
      getDevices()
        .then(async (res) => {
          if (res.ok) {
            const list: DeviceInfo[] = await res.json();
            populateFromList(list);
          }
        })
        .catch(() => {
          // Keep defaults if fetch fails
        });
    }
  }, [isOpen, initialDevices]);

  if (!isOpen) return null;

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

    try {
      const res = await testDeviceConnection(deviceName, ip, port);
      if (res.ok) {
        const data = await res.json();
        setTestResults((prev) => ({
          ...prev,
          [deviceName]: {
            loading: false,
            success: data.success,
            latency: data.latency_ms,
            message: data.message || (data.success ? "Kết nối tốt" : "Mất kết nối"),
          },
        }));
      } else {
        setTestResults((prev) => ({
          ...prev,
          [deviceName]: {
            loading: false,
            success: false,
            message: `Lỗi HTTP ${res.status}`,
          },
        }));
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
      handleTestSingle("CAM01", "USB_CAMERA", cameraIndex),
    ]);

    setFeedback({
      type: "info",
      msg: "Đã hoàn thành kiểm tra kết nối các thiết bị.",
    });
  };

  // Global Toggle All to Simulator or Real
  const handleSetGlobalMode = (mode: "REAL" | "SIM") => {
    const isSim = mode === "SIM";
    setRobotSim(isSim);
    setPlcSim(isSim);
    setUavSim(isSim);
    setCameraSim(isSim);
    setFeedback({
      type: "info",
      msg: `Đã chuyển toàn bộ thiết bị sang: ${
        isSim ? "🤖 SIMULATOR (Mô phỏng)" : "🔌 REAL HARDWARE (Phần cứng thực)"
      }. Nhấn 'LƯU CẤU HÌNH' để áp dụng.`,
    });
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
          ip_address: "USB_CAMERA",
          port: Number(cameraIndex),
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
            cameraIp: "USB_CAMERA",
            cameraPort: cameraIndex,
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

  return (
    <div className="hmi-modal-backdrop">
      <div className="hmi-modal-dialog config-modal">
        {/* Modal Header */}
        <div className="modal-header flex-between">
          <div className="modal-title-group">
            <h4>🛠️ CẤU HÌNH THIẾT BỊ PHẦN CỨNG LAN</h4>
            <span className="modal-subtitle">
              ROBOT FAIRINO FR3, PLC S7-1200 DB15, DRONE UAV & CAMERA QR
            </span>
          </div>
          <button
            type="button"
            className="btn-close-x"
            onClick={onClose}
            title="Đóng cửa sổ"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body config-modal-body">
          {/* Quick Preset Mode & Filter Bar */}
          <div className="config-toolbar-container">
            {/* Filter Tabs */}
            <div className="config-filter-tabs">
              <button
                type="button"
                className={`btn-tab-filter ${activeFilter === "ALL" ? "active" : ""}`}
                onClick={() => setActiveFilter("ALL")}
              >
                📋 Tất Cả (4 Thiết Bị)
              </button>
              <button
                type="button"
                className={`btn-tab-filter ${activeFilter === "ROBOT" ? "active" : ""}`}
                onClick={() => setActiveFilter("ROBOT")}
              >
                🤖 Robot FR3
              </button>
              <button
                type="button"
                className={`btn-tab-filter ${activeFilter === "PLC" ? "active" : ""}`}
                onClick={() => setActiveFilter("PLC")}
              >
                ⚡ PLC S7-1200
              </button>
              <button
                type="button"
                className={`btn-tab-filter ${activeFilter === "UAV" ? "active" : ""}`}
                onClick={() => setActiveFilter("UAV")}
              >
                🚁 UAV Drone
              </button>
              <button
                type="button"
                className={`btn-tab-filter ${activeFilter === "CAMERA" ? "active" : ""}`}
                onClick={() => setActiveFilter("CAMERA")}
              >
                📷 Camera QR
              </button>
            </div>

            {/* Quick Mode Preset */}
            <div className="config-quick-bar flex-between">
              <span className="quick-bar-lbl">
                ⚡ Đặt nhanh chế độ toàn trạm:
              </span>
              <div className="quick-btn-group">
                <button
                  type="button"
                  className={`btn-quick-mode ${
                    !uavSim && !robotSim && !plcSim && !cameraSim ? "active-real" : ""
                  }`}
                  onClick={() => handleSetGlobalMode("REAL")}
                  title="Đặt toàn bộ thiết bị sang chế độ kết nối phần cứng thực"
                >
                  🔌 Toàn Trạm REAL
                </button>
                <button
                  type="button"
                  className={`btn-quick-mode ${
                    uavSim && robotSim && plcSim && cameraSim ? "active-sim" : ""
                  }`}
                  onClick={() => handleSetGlobalMode("SIM")}
                  title="Đặt toàn bộ thiết bị sang chế độ Virtual Simulator"
                >
                  🤖 Toàn Trạm SIM
                </button>
              </div>
            </div>
          </div>

          {/* Feedback Banner */}
          {feedback && (
            <div className={`config-feedback-banner feedback-${feedback.type}`}>
              {feedback.msg}
            </div>
          )}

          {/* Device Cards Grid */}
          <div className="device-config-grid">
            {/* 1. ROBOT01 Card (FAIRINO FR3 Cobot) */}
            {showRobot && (
              <div className="device-config-card card-robot">
                <div className="device-card-header flex-between">
                  <div className="device-title">
                    <span className="dev-icon">🤖</span>
                    <strong>ROBOT01 (Fairino FR3 Cobot)</strong>
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
                      🔍 Ping
                    </button>
                  </div>
                </div>
                <div className="device-card-body">
                  <div className="form-grid-2">
                    <div className="form-group">
                      <label>Robot IP Address:</label>
                      <input
                        type="text"
                        className="hmi-input font-mono"
                        value={robotIp}
                        onChange={(e) => setRobotIp(e.target.value)}
                        placeholder="192.168.57.2"
                      />
                    </div>
                    <div className="form-group">
                      <label>Socket Server Port:</label>
                      <input
                        type="number"
                        className="hmi-input font-mono"
                        value={robotPort}
                        onChange={(e) => setRobotPort(Number(e.target.value))}
                        placeholder="8090"
                      />
                    </div>
                  </div>
                  <div className="sim-toggle-row flex-between">
                    <span className="lbl-sim">Chế độ vận hành:</span>
                    <div className="mode-pill-toggle">
                      <button
                        type="button"
                        className={`btn-mode-pill ${!robotSim ? "active-real" : ""}`}
                        onClick={() => setRobotSim(false)}
                      >
                        🔌 Real Hardware
                      </button>
                      <button
                        type="button"
                        className={`btn-mode-pill ${robotSim ? "active-sim" : ""}`}
                        onClick={() => setRobotSim(true)}
                      >
                        🤖 Simulator
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 2. PLC01 Card (Siemens S7-1200 Docking Station) */}
            {showPlc && (
              <div className="device-config-card card-plc">
                <div className="device-card-header flex-between">
                  <div className="device-title">
                    <span className="dev-icon">⚡</span>
                    <strong>PLC01 (Siemens S7-1200 Dock)</strong>
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
                      🔍 Ping
                    </button>
                  </div>
                </div>
                <div className="device-card-body">
                  <div className="form-grid-3">
                    <div className="form-group">
                      <label>PLC IP Address:</label>
                      <input
                        type="text"
                        className="hmi-input font-mono"
                        value={plcIp}
                        onChange={(e) => setPlcIp(e.target.value)}
                        placeholder="192.168.58.10"
                      />
                    </div>
                    <div className="form-group">
                      <label>Data Block (DB):</label>
                      <input
                        type="number"
                        className="hmi-input font-mono"
                        value={plcDbNumber}
                        onChange={(e) => setPlcDbNumber(Number(e.target.value))}
                        placeholder="15"
                      />
                    </div>
                    <div className="form-group">
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
                    </div>
                  </div>
                  <div className="sim-toggle-row flex-between">
                    <span className="lbl-sim">Chế độ vận hành:</span>
                    <div className="mode-pill-toggle">
                      <button
                        type="button"
                        className={`btn-mode-pill ${!plcSim ? "active-real" : ""}`}
                        onClick={() => setPlcSim(false)}
                      >
                        🔌 Real Hardware
                      </button>
                      <button
                        type="button"
                        className={`btn-mode-pill ${plcSim ? "active-sim" : ""}`}
                        onClick={() => setPlcSim(true)}
                      >
                        🤖 Simulator
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 3. UAV01 Card (Drone Delivery Unit) */}
            {showUav && (
              <div className="device-config-card card-uav">
                <div className="device-card-header flex-between">
                  <div className="device-title">
                    <span className="dev-icon">🚁</span>
                    <strong>UAV01 (Drone Controller)</strong>
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
                      🔍 Ping
                    </button>
                  </div>
                </div>
                <div className="device-card-body">
                  <div className="form-grid-2">
                    <div className="form-group">
                      <label>IP Address / Host:</label>
                      <input
                        type="text"
                        className="hmi-input font-mono"
                        value={uavIp}
                        onChange={(e) => setUavIp(e.target.value)}
                        placeholder="192.168.137.88"
                      />
                    </div>
                    <div className="form-group">
                      <label>MAVLink / UDP Port:</label>
                      <input
                        type="number"
                        className="hmi-input font-mono"
                        value={uavPort}
                        onChange={(e) => setUavPort(Number(e.target.value))}
                        placeholder="14550"
                      />
                    </div>
                  </div>
                  <div className="sim-toggle-row flex-between">
                    <span className="lbl-sim">Chế độ vận hành:</span>
                    <div className="mode-pill-toggle">
                      <button
                        type="button"
                        className={`btn-mode-pill ${!uavSim ? "active-real" : ""}`}
                        onClick={() => setUavSim(false)}
                      >
                        🔌 Real Hardware
                      </button>
                      <button
                        type="button"
                        className={`btn-mode-pill ${uavSim ? "active-sim" : ""}`}
                        onClick={() => setUavSim(true)}
                      >
                        🤖 Simulator
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 4. CAM01 Card (Camera QR Vision) */}
            {showCamera && (
              <div className="device-config-card card-cam">
                <div className="device-card-header flex-between">
                  <div className="device-title">
                    <span className="dev-icon">📷</span>
                    <strong>CAM01 (OpenCV Video Index {cameraIndex})</strong>
                  </div>
                  <div className="device-header-actions">
                    {renderTestBadge("CAM01")}
                    <button
                      type="button"
                      className="btn-ping-single"
                      onClick={() => handleTestSingle("CAM01", "USB_CAMERA", cameraIndex)}
                      disabled={testResults["CAM01"]?.loading}
                      title="Kiểm tra mở Camera OpenCV"
                    >
                      🔍 Ping
                    </button>
                  </div>
                </div>
                <div className="device-card-body">
                  <div className="form-group" style={{ marginBottom: "1rem" }}>
                    <label>OpenCV CAMERA_INDEX (Cổng Camera USB):</label>
                    <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                      <select
                        className="hmi-input font-mono"
                        value={cameraIndex}
                        onChange={(e) => setCameraIndex(Number(e.target.value))}
                        style={{ flex: 2 }}
                      >
                        <option value={0}>0 - Camera Mặc Định / Webcam 0 (Index 0)</option>
                        <option value={1}>1 - USB Camera Ngoài 1 (Index 1)</option>
                        <option value={2}>2 - USB Camera Ngoài 2 (Index 2)</option>
                        <option value={3}>3 - USB Camera Ngoài 3 (Index 3)</option>
                      </select>
                      <input
                        type="number"
                        min={0}
                        max={10}
                        className="hmi-input font-mono"
                        value={cameraIndex}
                        onChange={(e) => setCameraIndex(Number(e.target.value))}
                        style={{ width: "80px", textAlign: "center" }}
                        title="Chỉ số Index tùy chỉnh"
                        placeholder="0"
                      />
                    </div>
                    <small className="settings-input-hint" style={{ fontSize: "0.75rem", color: "#94a3b8", display: "block", marginTop: "4px" }}>
                      Chỉ số cổng thiết bị Video Capture trên máy chủ OpenCV (DirectShow)
                    </small>
                  </div>
                  <div className="sim-toggle-row flex-between">
                    <span className="lbl-sim">Chế độ vận hành:</span>
                    <div className="mode-pill-toggle">
                      <button
                        type="button"
                        className={`btn-mode-pill ${!cameraSim ? "active-real" : ""}`}
                        onClick={() => setCameraSim(false)}
                      >
                        🔌 Real Hardware
                      </button>
                      <button
                        type="button"
                        className={`btn-mode-pill ${cameraSim ? "active-sim" : ""}`}
                        onClick={() => setCameraSim(true)}
                      >
                        🤖 Simulator
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer Actions */}
        <div className="modal-footer flex-between">
          <button
            type="button"
            className="btn-hmi btn-secondary"
            onClick={handleTestAll}
            disabled={isSaving}
          >
            🔍 Test Toàn Bộ Kết Nối (Ping All)
          </button>

          <div className="flex-gap">
            <button
              type="button"
              className="btn-hmi btn-secondary"
              onClick={onClose}
              disabled={isSaving}
            >
              ĐÓNG
            </button>
            <button
              type="button"
              className="btn-hmi btn-primary"
              onClick={handleSaveAll}
              disabled={isSaving}
            >
              {isSaving ? (
                <>
                  <span className="spinner-mini"></span> Đang Lưu...
                </>
              ) : (
                "💾 LƯU CẤU HÌNH THIẾT BỊ"
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
