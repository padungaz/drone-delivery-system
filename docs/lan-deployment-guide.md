# LAN Deployment Guide

Hướng dẫn triển khai hệ thống Drone Delivery trên mạng nội bộ (không Internet).

---

## 1. Network Topology

```
                    WiFi Hotspot (Laptop AP)
                    192.168.137.1
                         │
        +────────────────+────────────────+
        │                │                │
   Backend PC       Raspberry Pi 5    Client Devices
   192.168.137.1    192.168.137.139   192.168.137.x
   Port 8000        Companion          React Dashboard
   (Laptop)         Headless           (any browser)
```

### Router Configuration

| Setting | Value |
|---------|-------|
| SSID | `DroneLAN` |
| Security | WPA2-PSK |
| Subnet | `192.168.2.0/24` |
| DHCP Range | `192.168.2.50 - 192.168.2.200` |
| Gateway | `192.168.2.1` |
| Internet | Disabled / Isolated |

### Static IP Assignments

| Device | IP | Notes |
|--------|----|-------|
| Backend Server (Laptop Hotspot) | `192.168.137.1` | Gateway/Server IP |
| Raspberry Pi 5 | `192.168.137.139` | Allocated via Hotspot DHCP |

---

## 2. Backend Server Setup (192.168.137.1)

### Requirements

- Windows 10/11 hoặc Linux
- Python 3.11+
- Port 8000 mở trên LAN

### Installation

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Verify

```bash
curl http://192.168.137.1:8000/health
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

## 3. Raspberry Pi 5 Setup (192.168.137.139)

### 3.1 Hardware Connections

| Connection | Pi Port | Notes |
|------------|---------|-------|
| Pixhawk TELEM1 TX | GPIO15 / RXD (pin 10) | TX↔RX chéo |
| Pixhawk TELEM1 RX | GPIO14 / TXD (pin 8)  | TX↔RX chéo |
| GND | GND (pin 6) | Common ground |
| CSI Camera | Camera port | CSI ribbon cable |
| Power | USB-C 5V/5A | Nguồn ổn định |

### 3.2 OS Configuration (Raspberry Pi OS Bookworm)

#### Enable UART (tắt Bluetooth để dùng /dev/ttyAMA0)

```bash
sudo raspi-config
# Interface Options → Serial Port
#   Login shell over serial: NO
#   Serial hardware enabled: YES
```

Hoặc edit trực tiếp `/boot/firmware/config.txt`:
```
enable_uart=1
dtoverlay=disable-bt
```

Reboot sau khi thay đổi:
```bash
sudo reboot
```

#### Set Static IP (Pi 5 dùng NetworkManager — không phải dhcpcd)

```bash
# Xem tên connection hiện tại
nmcli con show

# Đặt static IP (thay 'Preconfigured' bằng tên connection của bạn)
sudo nmcli con mod "Preconfigured" \
    ipv4.addresses 192.168.137.139/24 \
    ipv4.gateway 192.168.137.1 \
    ipv4.dns 192.168.137.1 \
    ipv4.method manual

sudo nmcli con up "Preconfigured"
hostname -I   # Kiểm tra IP mới
```

#### Add pi to dialout group (UART access)

```bash
sudo usermod -aG dialout rpi5
# Logout và login lại để có hiệu lực
```

### 3.3 Install Dependencies

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git

cd /opt/drone-delivery-system/companion
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Lưu ý:** `picamera2` cần cài riêng trên Pi:
> ```bash
> sudo apt install -y python3-picamera2
> # hoặc uncommment picamera2 trong requirements.txt
> ```

### 3.4 Configuration

Copy và edit `.env`:
```bash
cp .env.example .env
nano .env
```

```bash
SERVER_IP=192.168.137.1
MAVLINK_DEVICE=/dev/ttyAMA0
MAVLINK_BAUD=57600
```

### 3.5 MAVLink Quick Test

```bash
python3 -c "
from pymavlink import mavutil
conn = mavutil.mavlink_connection('/dev/ttyAMA0', baud=57600)
print('Waiting for heartbeat...')
conn.wait_heartbeat(timeout=30)
print('PX4 connected — system:', conn.target_system)
"
```

### 3.6 Auto-start (systemd)

```bash
# Cài tự động qua script
chmod +x install_service.sh
sudo ./install_service.sh

# Hoặc cài thủ công
sudo cp drone-companion.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable drone-companion
sudo systemctl start drone-companion
```

---

## 4. VS Code Remote SSH Development

### 4.1 Setup (1 lần)

1. Cài extension **Remote - SSH** trong VS Code (Microsoft)
2. `Ctrl+Shift+P` → `Remote-SSH: Connect to Host`
3. Nhập: `rpi5@192.168.137.139`
4. Chọn Linux khi được hỏi OS
5. VS Code Server tự động cài trên Pi

### 4.2 SSH Config (tùy chọn — để connect nhanh)

Thêm vào `~/.ssh/config` trên Laptop:

```
Host pi-drone
    HostName 192.168.137.139
    User rpi5
```

SSH không cần password:
```bash
ssh-copy-id rpi5@192.168.137.139
```

### 4.3 Workflow

Sau khi connect Remote SSH:
- Mở Folder: `/opt/drone-delivery-system`
- Terminal trong VS Code → terminal chạy trực tiếp trên Pi
- Chỉnh code → tự động save lên Pi
- Chạy `python main.py` từ VS Code terminal

---

## 5. Frontend Dashboard

### Development

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
# Truy cập: http://192.168.137.1:5173
```

### Production Build

```bash
npm run build
# Serve dist/ via nginx hoặc copy vào backend static files
```

### Environment Variables

Tạo `frontend/.env`:

```
VITE_API_URL=http://192.168.137.1:8000
VITE_WS_URL=ws://192.168.137.1:8000/ws/client
VITE_DRONE_ID=drone-01
```

---

## 6. Pixhawk 6C Setup

### Wiring

```
Pixhawk TELEM1     ──►    Pi GPIO UART
   TX  (pin 2)    ──────► GPIO15/RXD (pin 10)
   RX  (pin 3)    ◄──────  GPIO14/TXD (pin 8)
   GND (pin 6)    ──────── GND        (pin 6)
```

### PX4 Parameters (via QGroundControl)

Apply tất cả parameters từ [px4-parameters.md](px4-parameters.md).

Quan trọng nhất:
- `SER_TEL1_BAUD = 57600`
- `MAV_1_CONFIG = TELEM1`
- `COM_OBC_LOSS_T = 5` (companion heartbeat timeout)

---

## 7. Communication Flow Test

### Step 1: Backend Health Check

```bash
curl http://192.168.137.1:8000/health
```

### Step 2: Pi WebSocket Connection

```bash
# Trên Pi:
python main.py

# Expect:
# [INFO] WebSocket connected to ws://192.168.137.1:8000/ws/drone/drone-01
```

### Step 3: Telemetry

Dashboard frontend cập nhật telemetry mỗi 2 giây.

### Step 4: Mission Start

Nhấn **START MISSION** trên Dashboard. Verify:
- Backend log: `Mission started for drone drone-01`
- Pi log: `Received command: START_MISSION`
- Pi log: `State transition: IDLE → ARMING`
- Pixhawk arming → Drone cất cánh

---

## 8. Troubleshooting

| Issue | Check |
|-------|-------|
| Pi không connect WS | Ping `192.168.137.1`, firewall port 8000 |
| MAVLink timeout | UART wiring (TX↔RX chéo), baudrate `SER_TEL1_BAUD=57600` |
| `/dev/ttyAMA0` không tồn tại | Enable UART trong `raspi-config`, thêm `enable_uart=1` |
| Permission denied UART | `sudo usermod -aG dialout rpi5`, logout/login lại |
| Pi IP sai | `nmcli con mod` để set static IP (không dùng `dhcpcd` trên Pi 5 Bookworm) |
| ArUco không detect | Camera cable, marker 15cm, ID=0, lighting |
| Telemetry không hiện | Pi logs, WS connection, `drone-01` ID match |
| STOP bị reject | Drone phải LANDED + DISARMED |
| PX4 failsafe RTL | `COM_OBC_LOSS_T=5`, kiểm tra Pi companion đang chạy |

### Log Locations

| Component | Log |
|-----------|-----|
| Backend | stdout / uvicorn console |
| Companion | `/var/log/drone-companion.log` hoặc `journalctl -u drone-companion -f` |
| PX4 | QGroundControl → Analyze Tools → MAVLink Inspector |

---

## 9. Security Notes (LAN)

- Không expose port 8000 ra Internet
- Dùng WPA2 trên WiFi `DroneLAN`
- Isolated VLAN nếu có switch managed
- Không lưu `.env` vào git (đã có trong `.gitignore`)
- SSH key authentication thay vì password (dùng `ssh-copy-id`)

---

## 10. Pre-Flight Checklist

- [ ] Router `DroneLAN` hoặc Hotspot hoạt động
- [ ] Backend `192.168.137.1:8000` health OK
- [ ] Pi `192.168.137.139` — ping OK từ Laptop
- [ ] SSH vào Pi thành công (rpi5@192.168.137.139)
- [ ] `.env` đã set `SERVER_IP` và `MAVLINK_DEVICE` đúng
- [ ] `python main.py` → PX4 heartbeat received trong log
- [ ] WebSocket connected trong log Pi
- [ ] Dashboard telemetry updating mỗi 2 giây
- [ ] GPS fix ≥ 6 satellites
- [ ] Battery > 50%
- [ ] ArUco markers đặt tại pickup và drop
- [ ] PX4 parameters applied via QGroundControl
- [ ] FORCE RTL tested
- [ ] Khu vực bay clear

---

## 11. Multi-Drone Extension

Để hỗ trợ nhiều drone:

1. Gán `DRONE_ID` riêng trong `.env` mỗi Pi (`drone-01`, `drone-02`, ...)
2. Static IP riêng (`192.168.137.139`, `192.168.137.140`, ...)
3. Mỗi Pi connect tới `ws://192.168.137.1:8000/ws/drone/{drone_id}`
4. Frontend chọn active drone qua `VITE_DRONE_ID`

Backend đã hỗ trợ multiple WebSocket connections theo `drone_id`.
