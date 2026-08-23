import { useState } from "react";
import type { DeviceInfo } from "../types/drone";
import { updateDeviceConfig, testDeviceConnection } from "../services/api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  devices: DeviceInfo[];
  onRefreshDevices?: () => void;
}

export function DeviceConfigModal({ isOpen, onClose, devices, onRefreshDevices }: Props) {
  const [selectedDeviceName, setSelectedDeviceName] = useState<string>("ROBOT01");
  const [ipAddress, setIpAddress] = useState<string>("192.168.57.2");
  const [port, setPort] = useState<number>(8090);
  const [simMode, setSimMode] = useState<boolean>(false);
  const [dbNumber, setDbNumber] = useState<number>(15);

  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  // Auto-populate form when selecting a device
  const handleSelectDeviceChange = (name: string) => {
    setSelectedDeviceName(name);
    const dev = devices.find((d) => d.device_name === name);
    if (dev) {
      setIpAddress(dev.ip_address || "192.168.57.2");
      setPort(dev.port || (name.includes("PLC") ? 102 : 8090));
      setSimMode(dev.simulator_mode ?? false);
      setDbNumber(dev.db_number || 15);
    }
  };

  const handleSaveConfig = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await updateDeviceConfig(selectedDeviceName, {
        ip_address: ipAddress,
        port: Number(port),
        simulator_mode: simMode,
        db_number: Number(dbNumber),
      });
      if (res.ok) {
        const updated = await res.json();
        setMsg(`✅ Đã lưu cấu hình thiết bị ${selectedDeviceName} (IP: ${updated.ip_address}:${updated.port}, Mode: ${updated.simulator_mode ? "Simulator" : "Real"}) thành công!`);
        if (onRefreshDevices) onRefreshDevices();
      } else {
        const err = await res.text();
        setMsg(`❌ Lỗi lưu cấu hình: ${err}`);
      }
    } catch (err) {
      setMsg(`❌ Lỗi: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await testDeviceConnection(selectedDeviceName, ipAddress, Number(port));
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          setMsg(`✅ Test kết nối thành công: ${data.message} (Độ trễ: ${data.latency_ms}ms)`);
        } else {
          setMsg(`❌ Test kết nối thất bại: ${data.message}`);
        }
      } else {
        setMsg("❌ Không thể kiểm tra kết nối thiết bị");
      }
    } catch (err) {
      setMsg(`❌ Lỗi test kết nối: ${err instanceof Error ? err.message : "Thất bại"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" style={{ zIndex: 1100 }}>
      <div className="modal-content panel" style={{ maxWidth: "680px", width: "95%", border: "1px solid #00F0FF" }}>
        <div className="panel-header-inline" style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.1)", paddingBottom: "10px" }}>
          <h3 style={{ color: "#00F0FF", display: "flex", alignItems: "center", gap: "8px" }}>
            ⚙️ Cấu Hình Thiết Bị Hardware LAN
          </h3>
          <button type="button" className="btn btn-outline btn-sm" onClick={onClose}>
            ✖ Đóng
          </button>
        </div>

        {/* Device Connection Configuration Form */}
        <div style={{ marginTop: "1rem" }}>
          <p style={{ margin: "0 0 12px 0", color: "#94a3b8", fontSize: "0.85rem" }}>
            Tùy chỉnh thông tin địa chỉ IP, Cổng Socket Port và Chế độ vận hành (Mô phỏng Simulator / Thật Hardware) cho các thiết bị kết nối.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            <div style={{ gridColumn: "span 2" }}>
              <label style={{ fontSize: "0.8rem", color: "#94a3b8", fontWeight: "bold" }}>CHỌN THIẾT BỊ CẦN CẤU HÌNH</label>
              <select
                className="form-control"
                value={selectedDeviceName}
                onChange={(e) => handleSelectDeviceChange(e.target.value)}
                style={{ background: "#0f172a", color: "#00F0FF", fontWeight: "bold", fontSize: "0.95rem" }}
              >
                <option value="ROBOT01">🤖 ROBOT01 (Fairino Cobot FR3)</option>
                <option value="PLC01">⚡ PLC01 (Siemens S7-1200)</option>
                <option value="UAV01">🚁 UAV01 (Drone Controller)</option>
                <option value="CAM01">📷 CAM01 (QR Reader Vision)</option>
              </select>
            </div>

            {selectedDeviceName === "CAM01" ? (
              <div style={{ gridColumn: "span 2" }}>
                <label style={{ fontSize: "0.8rem", color: "#94a3b8" }}>CHỌN CAMERA INDEX (OPENCV DIRECTSHOW)</label>
                <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                  <select
                    className="form-control"
                    value={port}
                    onChange={(e) => setPort(Number(e.target.value))}
                    style={{ flex: 1, background: "#0f172a", color: "#00F0FF" }}
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
                    className="form-control"
                    value={port}
                    onChange={(e) => setPort(Number(e.target.value))}
                    style={{ width: "80px", textAlign: "center" }}
                    placeholder="0"
                  />
                </div>
                <small style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "4px", display: "block" }}>
                  Chỉ số cổng thiết bị Camera nhận diện OpenCV (DirectShow / V4L2)
                </small>
              </div>
            ) : (
              <>
                <div>
                  <label style={{ fontSize: "0.8rem", color: "#94a3b8" }}>ĐỊA CHỈ IP LAN</label>
                  <input
                    type="text"
                    className="form-control"
                    value={ipAddress}
                    onChange={(e) => setIpAddress(e.target.value)}
                    placeholder="VD: 192.168.57.2"
                  />
                </div>

                <div>
                  <label style={{ fontSize: "0.8rem", color: "#94a3b8" }}>CỔNG SOCKET (PORT)</label>
                  <input
                    type="number"
                    className="form-control"
                    value={port}
                    onChange={(e) => setPort(Number(e.target.value))}
                    placeholder="8090"
                  />
                </div>
              </>
            )}

            {selectedDeviceName.includes("PLC") && (
              <div>
                <label style={{ fontSize: "0.8rem", color: "#94a3b8" }}>SỐ DB (DATA BLOCK)</label>
                <input
                  type="number"
                  className="form-control"
                  value={dbNumber}
                  onChange={(e) => setDbNumber(Number(e.target.value))}
                  placeholder="15"
                />
              </div>
            )}

            <div>
              <label style={{ fontSize: "0.8rem", color: "#94a3b8" }}>CHẾ ĐỘ VẬN HÀNH</label>
              <div style={{ marginTop: "8px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", color: simMode ? "#ffb800" : "#10b981" }}>
                  <input
                    type="checkbox"
                    checked={simMode}
                    onChange={(e) => setSimMode(e.target.checked)}
                  />
                  <b style={{ fontSize: "0.9rem" }}>{simMode ? "🤖 Simulator (Mô phỏng)" : "🔌 Real Hardware (Thật)"}</b>
                </label>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "1.5rem" }}>
            <button
              type="button"
              className="btn btn-outline"
              onClick={handleTestConnection}
              disabled={loading}
            >
              🔍 Test Ping Connection
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSaveConfig}
              disabled={loading}
            >
              💾 Lưu Cấu Hình
            </button>
          </div>

          {msg && (
            <div style={{ marginTop: "12px", padding: "10px", background: "rgba(0, 240, 255, 0.1)", border: "1px solid #00F0FF", borderRadius: "6px", fontSize: "0.85rem" }}>
              {msg}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
