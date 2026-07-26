import type { DeviceInfo } from "../types/drone";

interface Props {
  devices: DeviceInfo[];
}

export function DeviceStatusPanel({ devices }: Props) {
  return (
    <div className="panel device-status-panel">
      <h3>🌐 Mạng Thiết bị LAN (Hardware Status)</h3>
      <div className="table-responsive">
        <table className="device-table">
          <thead>
            <tr>
              <th>Thiết bị</th>
              <th>Loại</th>
              <th>Địa chỉ IP</th>
              <th>Trạng thái</th>
              <th>Heartbeat cuối</th>
            </tr>
          </thead>
          <tbody>
            {devices.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center">Đang tải dữ liệu thiết bị...</td>
              </tr>
            ) : (
              devices.map((dev) => {
                const statusClass =
                  dev.status === "ONLINE"
                    ? "status-online"
                    : dev.status === "BUSY"
                    ? "status-busy"
                    : "status-offline";

                return (
                  <tr key={dev.device_name}>
                    <td className="font-bold">{dev.device_name}</td>
                    <td><span className="device-tag">{dev.device_type}</span></td>
                    <td><code>{dev.ip_address}</code></td>
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
