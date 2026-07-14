# LAN Deployment Guide

Hướng dẫn triển khai hệ thống Drone Delivery trên mạng nội bộ (không Internet).

---

## 1. Network Topology

```
                    WiFi Router (DroneLAN)
                    192.168.2.1
                         |
        +----------------+----------------+
        |                |                |
   Backend PC       Raspberry Pi      Client Devices
   192.168.2.28     192.168.2.100     192.168.2.x
   Port 8000        Companion          React Dashboard
```

### Router Configuration

| Setting | Value |
|---------|-------|
| SSID | `DroneLAN` |
| Security | WPA2-PSK (recommended) |
| Subnet | `192.168.2.0/24` |
| DHCP Range | `192.168.2.50 - 192.168.2.200` |
| Gateway | `192.168.2.1` |
| DNS | Not required (offline LAN) |
| Internet | Disabled / Isolated |

### Static IP Assignments

| Device | IP | MAC Reservation |
|--------|-----|-----------------|
| Backend Server | `192.168.2.28` | Reserve in router DHCP |
| Raspberry Pi 5 | `192.168.2.100` | Reserve in router DHCP |

---

## 2. Backend Server Setup (192.168.2.28)

### Requirements

- Windows 10/11 or Linux
- Python 3.11+
- Port 8000 open on LAN

### Installation

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Verify

```bash
curl http://192.168.2.28:8000/health
# {"status":"ok","service":"drone-delivery-backend"}
```

### Windows Firewall

```powershell
New-NetFirewallRule -DisplayName "Drone Backend" -Direction Inbound -Port 8000 -Protocol TCP -Action Allow
```

### Auto-start (Linux systemd)

```ini
# /etc/systemd/system/drone-backend.service
[Unit]
Description=Drone Delivery Backend
After=network.target

[Service]
Type=simple
User=drone
WorkingDirectory=/opt/drone-delivery-system/backend
ExecStart=/opt/drone-delivery-system/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable drone-backend
sudo systemctl start drone-backend
```

---

## 3. Raspberry Pi 5 Setup (192.168.2.100)

### Hardware Connections

| Connection | Port |
|------------|------|
| Pixhawk TELEM1 | UART GPIO14/15 (`/dev/ttyAMA0`) |
| CSI Camera | Camera port |
| Power | 5V 5A USB-C |

### OS Configuration

```bash
# Enable UART (disable Bluetooth on GPIO serial)
sudo raspi-config
# Interface Options → Serial Port → Login shell: No → Serial hardware: Yes

# Set static IP
sudo nano /etc/dhcpcd.conf
```

```
interface wlan0
static ip_address=192.168.2.100/24
static routers=192.168.2.1
```

### Install Dependencies

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv libcamera-dev

cd /opt/drone-delivery-system/companion
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Edit `companion/config.py`:

```python
SERVER_IP = "192.168.2.28"
SERVER_PORT = 8000
MAVLINK_DEVICE = "/dev/ttyAMA0"
MAVLINK_BAUD = 57600
```

### MAVLink Test

```bash
python3 -c "
from pymavlink import mavutil
conn = mavutil.mavlink_connection('/dev/ttyAMA0', baud=57600)
conn.wait_heartbeat()
print('PX4 connected:', conn.target_system)
"
```

### Auto-start (systemd)

```ini
# /etc/systemd/system/drone-companion.service
[Unit]
Description=Drone Companion Computer
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/drone-delivery-system/companion
ExecStart=/opt/drone-delivery-system/companion/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable drone-companion
sudo systemctl start drone-companion
```

---

## 4. Frontend Dashboard

### Development

```bash
cd frontend
npm install
npm run dev
# Access: http://192.168.2.x:5173
```

### Production Build

```bash
npm run build
# Serve dist/ via nginx or copy to backend static files
```

### Environment Variables

Create `frontend/.env`:

```
VITE_API_URL=http://192.168.2.28:8000
VITE_WS_URL=ws://192.168.2.28:8000/ws/client
VITE_DRONE_ID=drone-01
```

---

## 5. Pixhawk 6C Setup

### Wiring

```
Pixhawk TELEM1 ──► Pi GPIO UART (TX↔RX crossed)
Pixhawk POWER  ──► Power Module / Battery
GPS Module     ──► GPS1 port
Range Finder   ──► Optional (for EKF2_HGT_MODE)
```

### PX4 Parameters

Apply all parameters from [px4-parameters.md](px4-parameters.md) via QGroundControl.

### Verify Precision Landing

1. Set `PLD_HACC_RAD = 0.2`
2. Place ArUco marker (ID 0, 15cm) at landing pad
3. Test in `AUTO.PRECLAND` mode before full mission

---

## 6. Communication Flow Test

### Step 1: Backend Health

```bash
curl http://192.168.2.28:8000/health
```

### Step 2: Pi WebSocket Connection

Check backend logs for:
```
Drone connected: drone-01
```

### Step 3: Telemetry

Check dashboard — telemetry should update every 2 seconds.

### Step 4: Mission Command (Initial Start)

Press **START MISSION** in dashboard. Verify:
- Backend logs: `Mission started for drone drone-01`
- Pi logs: `Received command: START_MISSION`
- Pi logs: `State transition: IDLE -> ARMING`
- Pixhawk arming sequence completes.
- Drone climbs to takeoff altitude and flies to pickup location.

### Step 5: Pickup Confirmation Gate

When the drone arrives at the pickup location, performs precision landing, and lands:
- Verify PX4 status: `Landed` and automatically `Disarmed` (Auto-Disarm).
- Dashboard State shows: `WAIT_PICKUP_CONFIRM`.
- Dashboard banner displays: `"Package ready at pickup location — press PICKUP OK when package is secured"`.
- Verify the **PICKUP OK** button is **ENABLED** (other buttons like START are DISABLED).
- Click **PICKUP OK**. Verify:
  - Pi logs: `PICKUP_COMPLETE received — arming for drop phase`
  - Drone arms, takes off, and flies to the drop location.

### Step 6: Drop Confirmation Gate

When the drone arrives at the drop location, performs precision landing, and lands:
- Verify PX4 status: `Landed` and automatically `Disarmed`.
- Dashboard State shows: `WAIT_DROP_CONFIRM`.
- Dashboard banner displays: `"Package delivered at drop location — press DROP OK to confirm delivery"`.
- Verify the **DROP OK** button is **ENABLED**.
- Click **DROP OK**. Verify:
  - Pi logs: `DROP_COMPLETE received — arming for return home`
  - Drone arms, takes off, and enters `RETURN_HOME` (RTL).

### Step 7: Continuous Delivery Intercept (Optional)

During the `RETURN_HOME` phase, the **START MISSION** button becomes **ENABLED** again:
- Enter new pickup/drop coordinates and click **START MISSION**.
- Verify Pi logs: `Continuous Delivery: queuing next mission during RETURN_HOME`.
- As soon as the drone lands and auto-disarms at home, it immediately transition to `ARMING` and starts the next mission without returning to `IDLE`.

### Step 8: Force RTL

Press **FORCE RETURN HOME** at any flying state. Verify PX4 immediately enters `AUTO.RTL` mode and the FSM changes to `RETURN_HOME`.

---

## 7. Multi-Drone Extension

To support multiple drones:

1. Assign unique `drone_id` per Pi (`drone-01`, `drone-02`, ...)
2. Set static IP per Pi (`192.168.2.100`, `192.168.2.101`, ...)
3. Each Pi connects to `ws://192.168.2.28:8000/ws/drone/{drone_id}`
4. Frontend selects active drone via `VITE_DRONE_ID`

Backend already supports multiple drone WebSocket connections keyed by `drone_id`.

---

## 8. Troubleshooting

| Issue | Check |
|-------|-------|
| Pi không kết nối WS | Ping `192.168.2.28`, firewall port 8000 |
| MAVLink timeout | UART wiring, `SER_TEL1_BAUD=57600`, `/dev/ttyAMA0` permissions |
| ArUco không detect | Camera cable, marker size 15cm, ID=0, lighting |
| Telemetry không hiện | Pi logs, WS connection, `drone-01` ID match |
| STOP bị reject | Drone phải LANDED + DISARMED |
| PX4 failsafe | `COM_OBC_LOSS_T=5`, kiểm tra Pi companion đang chạy |

### Log Locations

| Component | Log |
|-----------|-----|
| Backend | stdout / uvicorn console |
| Companion | `/var/log/drone-companion.log` |
| PX4 | QGroundControl → Analyze Tools → MAVLink Inspector |

---

## 9. Security Notes (LAN)

- Không expose port 8000 ra Internet
- Dùng WPA2 trên WiFi `DroneLAN`
- Isolated VLAN nếu có switch managed
- Không lưu credentials trong repo

---

## 10. Pre-Flight Checklist

- [ ] Router `DroneLAN` hoạt động
- [ ] Backend `192.168.2.28:8000` health OK
- [ ] Pi `192.168.2.100` connected WebSocket
- [ ] MAVLink heartbeat OK
- [ ] GPS fix ≥ 6 satellites
- [ ] Battery > 50%
- [ ] ArUco markers đặt tại pickup và drop
- [ ] PX4 parameters applied
- [ ] Dashboard telemetry updating
- [ ] FORCE RTL tested
- [ ] Khu vực bay clear
