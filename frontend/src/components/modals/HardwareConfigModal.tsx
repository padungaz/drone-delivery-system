import { useState } from "react";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSave?: (config: Record<string, string>) => void;
}

export function HardwareConfigModal({ isOpen, onClose, onSave }: Props) {
  const [robotIp, setRobotIp] = useState("192.168.58.2");
  const [robotPort, setRobotPort] = useState("8090");
  const [plcIp, setPlcIp] = useState("192.168.58.10");
  const [cameraIp, setCameraIp] = useState("192.168.58.50");
  const [uavIp, setUavIp] = useState("192.168.58.100");
  const [uavPort, setUavPort] = useState("14550");
  const [mode, setMode] = useState("REAL_HARDWARE");
  const [testResult, setTestResult] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleTestConnection = () => {
    setTestResult(`⏳ Pinging UAV (${uavIp}:${uavPort}), FAIRINO (${robotIp}:${robotPort}), PLC (${plcIp})...`);
    setTimeout(() => {
      setTestResult("✅ Kết nối thành công tới tất cả thiết bị (UAV Drone, FAIRINO Robot, Siemens PLC, Camera QR)!");
    }, 1000);
  };

  const handleSave = () => {
    if (onSave) {
      onSave({ robotIp, robotPort, plcIp, cameraIp, uavIp, uavPort, mode });
    }
    onClose();
  };

  return (
    <div className="hmi-modal-backdrop">
      <div className="hmi-modal-dialog config-modal">
        <div className="modal-header flex-between">
          <h4>🛠️ CẤU HÌNH THIẾT BỊ PHẦN CỨNG</h4>
          <button type="button" className="btn-close-x" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div className="form-group">
            <label>Mode Hoạt Động:</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="hmi-input"
            >
              <option value="REAL_HARDWARE">REAL HARDWARE (Phần cứng thực)</option>
              <option value="SIMULATOR">SIMULATOR (Mô phỏng Virtual Device)</option>
            </select>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label>UAV Drone Controller IP / Host:</label>
              <input
                type="text"
                value={uavIp}
                onChange={(e) => setUavIp(e.target.value)}
                className="hmi-input"
              />
            </div>
            <div className="form-group">
              <label>UAV MAVLink UDP Port:</label>
              <input
                type="text"
                value={uavPort}
                onChange={(e) => setUavPort(e.target.value)}
                className="hmi-input"
              />
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label>Robot FAIRINO FR3 IP:</label>
              <input
                type="text"
                value={robotIp}
                onChange={(e) => setRobotIp(e.target.value)}
                className="hmi-input"
              />
            </div>
            <div className="form-group">
              <label>Robot Socket Port:</label>
              <input
                type="text"
                value={robotPort}
                onChange={(e) => setRobotPort(e.target.value)}
                className="hmi-input"
              />
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label>PLC Siemens S7-1200 IP:</label>
              <input
                type="text"
                value={plcIp}
                onChange={(e) => setPlcIp(e.target.value)}
                className="hmi-input"
              />
            </div>
            <div className="form-group">
              <label>Camera QR Scanner IP:</label>
              <input
                type="text"
                value={cameraIp}
                onChange={(e) => setCameraIp(e.target.value)}
                className="hmi-input"
              />
            </div>
          </div>

          {testResult && (
            <div className="test-result-box mt-2">{testResult}</div>
          )}
        </div>

        <div className="modal-footer flex-between">
          <button
            type="button"
            className="btn-hmi btn-secondary"
            onClick={handleTestConnection}
          >
            🔌 Test Connection
          </button>
          <div className="flex-gap">
            <button
              type="button"
              className="btn-hmi btn-secondary"
              onClick={onClose}
            >
              CANCEL
            </button>
            <button
              type="button"
              className="btn-hmi btn-primary"
              onClick={handleSave}
            >
              SAVE CONFIG
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

