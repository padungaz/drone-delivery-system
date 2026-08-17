import type { DeviceInfo } from "../types/drone";

interface Props {
  devices: DeviceInfo[];
  onOpenConfig?: () => void;
}

export function DeviceStatusPanel({ devices, onOpenConfig }: Props) {
  return (
    <div className="panel device-status-panel">
      <div className="panel-header-inline">
        <h3>🌐 Mạng Thiết bị LAN (Hardware Connection Status)</h3>
        {onOpenConfig && (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={onOpenConfig}
            style={{ display: "flex", alignItems: "center", gap: "6px" }}
          >
            ⚙️ Cấu hình
          </button>
        )}
      </div>
      <div className="table-responsive" style={{ marginTop: "8px" }}>
        <table className="device-table">
          <thead>
            <tr>
              <th>Thiết bị</th>
              <th>Loại</th>
              <th>Địa chỉ IP : Port</th>
              <th>Vận hành</th>
              <th>Trạng thái</th>
              <th>Heartbeat cuối</th>
            </tr>
          </thead>
          <tbody>
            {devices.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center">Đang tải dữ liệu thiết bị...</td>
              </tr>
            ) : (
              devices.map((dev) => {
                const statusClass =
                  dev.status === "ONLINE"
                    ? "status-online"
                    : dev.status === "BUSY"
                    ? "status-busy"
                    : "status-offline";

                const portText = dev.port ? `:${dev.port}` : (dev.device_name === "PLC01" ? ":102" : dev.device_name === "ROBOT01" ? ":8090" : "");

                return (
                  <tr key={dev.device_name}>
                    <td className="font-bold">{dev.device_name}</td>
                    <td><span className="device-tag">{dev.device_type}</span></td>
                    <td><code>{dev.ip_address}{portText}</code></td>
                    <td>
                      <span className={`status-badge ${dev.simulator_mode ? "status-busy" : "status-online"}`} style={{ fontSize: "0.75rem" }}>
                        {dev.simulator_mode ? "SIMULATOR" : "REAL HARDWARE"}
                      </span>
                    </td>
                    <td>
                      <span className={`status-badge ${statusClass}`}>
                        {dev.status}
                      </span>
                    </td>
                    <td className="text-sm">
                      {new Date(dev.last_heartbeat).toLocaleTimeString()}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

