# RUNBOOK — Drone Delivery System

Hướng dẫn vận hành, debug, và troubleshooting hệ thống Drone Delivery
trên môi trường Raspberry Pi 5 thực tế (headless).

---

## TÓM TẮT TRẠNG THÁI HỆ THỐNG

| Component | Trạng thái |
|-----------|-----------|
| Backend (FastAPI + SQLite) | ✅ Hoạt động |
| Frontend (React + Vite) | ✅ Hoạt động |
| Companion (Raspberry Pi 5) | ✅ Triển khai thực tế |
| MAVLink (Pixhawk 6C UART) | ✅ `/dev/ttyAMA0` |
| Vision / ArUco Landing | 🔶 Đang phát triển |
| PX4 End-to-End Flight | 🔶 Giai đoạn test |

---

## 1. KIẾN TRÚC PHẦN CỨNG

```
Laptop / PC Developer
        │
        │  VS Code Remote SSH (SSH over LAN/WiFi Hotspot)
        ▼
Raspberry Pi 5  (192.168.137.139)
        │
        │  MAVLink UART — /dev/ttyAMA0 — 57600 baud
        │  (Pixhawk TELEM1 ↔ Pi GPIO14/15)
        ▼
Pixhawk 6C  (PX4 Firmware)
        │
        ├── GPS Module
        ├── MTF-02P Rangefinder
        └── Motors / ESCs
```

---

## 2. PHÁT TRIỂN QUA VS CODE REMOTE SSH

### 2.1 Cài đặt VS Code Remote SSH

1. Cài extension **Remote - SSH** trong VS Code
2. `Ctrl+Shift+P` → `Remote-SSH: Connect to Host`
3. Nhập: `rpi5@192.168.137.139`
4. Lần đầu sẽ copy SSH key và cài VS Code Server tự động

### 2.2 Mở project trên Pi

Trong VS Code sau khi connect:
- `File → Open Folder` → `/opt/drone-delivery-system`

Bây giờ bạn có thể:
- ✅ Chỉnh sửa code trực tiếp trên Pi
- ✅ Mở Terminal → chạy lệnh trên Pi
- ✅ Xem log realtime trong terminal VS Code

### 2.3 SSH thủ công (Terminal)

```bash
ssh rpi5@192.168.137.139

# Tạo SSH alias để connect nhanh (thêm vào ~/.ssh/config trên Laptop)
Host pi-drone
    HostName 192.168.137.139
    User rpi5
    IdentityFile ~/.ssh/id_rsa

# Sau đó dùng:
ssh pi-drone
```

---

## 3. CÀI ĐẶT TRÊN RASPBERRY PI

### 3.1 Cài lần đầu (chạy 1 lần)

```bash
# SSH vào Pi
ssh rpi5@192.168.137.139

# Clone project (nếu chưa có)
git clone https://github.com/padungaz/drone-delivery-system.git /opt/drone-delivery-system
cd /opt/drone-delivery-system/companion

# Cài tự động qua install script
chmod +x install_service.sh
sudo ./install_service.sh
```

### 3.2 Cấu hình .env

```bash
nano /opt/drone-delivery-system/companion/.env
```

```bash
SERVER_IP=192.168.137.1          # IP laptop/PC hotspot
SERVER_PORT=8000
DRONE_ID=drone-01
MAVLINK_DEVICE=/dev/ttyAMA0     # hoặc /dev/ttyUSB0
MAVLINK_BAUD=57600
LOG_FILE=/var/log/drone-companion.log
LOG_LEVEL=INFO
```

### 3.3 Enable UART trên Raspberry Pi 5

```bash
sudo raspi-config
# Interface Options → Serial Port
#   Login shell over serial: NO
#   Serial hardware enabled: YES
```

Hoặc thêm vào `/boot/firmware/config.txt`:
```
enable_uart=1
dtoverlay=disable-bt
```

Sau đó reboot:
```bash
sudo reboot
```

Kiểm tra UART available:
```bash
ls -la /dev/ttyAMA0
# crw-rw---- 1 root dialout ... /dev/ttyAMA0
```

---

## 4. CHẠY HỆ THỐNG

### 4.1 Backend (Laptop/PC)

**Windows PowerShell:**
```powershell
cd backend
.\venv\Scripts\Activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Hoặc chạy trực tiếp không cần activate:
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Linux / Mac / Pi:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Kiểm tra:**
```bash
curl http://192.168.137.1:8000/health
# {"status":"ok","service":"drone-delivery-backend"}
```

### 4.2 Frontend (Laptop/PC)

```bash
cd frontend
npm run dev -- --host 0.0.0.0
# Truy cập: http://192.168.137.1:5173
```

### 4.3 Companion (Raspberry Pi — thủ công)

```bash
ssh rpi5@192.168.137.139
cd /opt/drone-delivery-system/companion
source venv/bin/activate
python main.py
```

### 4.4 Test Camera + ArUco Detection (từ Frontend)

**Yêu cầu:** Backend đang chạy, Companion đang chạy (đã kết nối WebSocket), camera USB đã cắm vào Pi.

1. Mở Dashboard frontend: `http://192.168.137.1:5173`
2. Nhấn nút **📷 Test Camera** trong panel "Camera & ArUco"
3. Trạng thái sẽ chuyển từ 🔴 Camera OFF → 🟢 Camera ON
4. Đưa mã ArUco (DICT_4X4_50, ID=0) ra trước camera USB
5. Dashboard sẽ hiển thị: Marker ID, Offset X/Y, Center X/Y (cập nhật mỗi 2 giây)
6. Nhấn **⏹ Stop Camera** để tắt

**Log trên Pi khi camera bật thành công:**
```
[CAMERA] Starting camera...
[CAMERA] Device: /dev/video0
[CAMERA] Resolution: 640x480
[CAMERA] FPS: 30
[CAMERA] ArUco dictionary: DICT_4X4_50
[CAMERA] Camera started successfully
[CAMERA] ArUco detection thread started
```

**Kiểm tra thủ công qua API (không cần frontend):**
```bash
# Bật camera
curl -X POST http://192.168.137.1:8000/camera/start?drone_id=drone-01

# Tắt camera
curl -X POST http://192.168.137.1:8000/camera/stop?drone_id=drone-01
```

Log khởi động dự kiến:
```
============================================================
Drone Delivery Companion — Raspberry Pi 5
============================================================
[INFO] Pi hostname  : raspberrypi
[INFO] Pi IP        : 192.168.137.139
[INFO] Drone ID     : drone-01
[INFO] MAVLink dev  : /dev/ttyAMA0  @ 57600 baud
[INFO] Backend      : http://192.168.137.1:8000
[INFO] WebSocket    : ws://192.168.137.1:8000/ws/drone/drone-01
[INFO] Log file     : /var/log/drone-companion.log
[INFO] Mission state: IDLE
============================================================
[INFO] Waiting for PX4 heartbeat (timeout=30s)...
[INFO] PX4 heartbeat received — system=1 component=1
[INFO] WebSocket connected to ws://192.168.137.1:8000/ws/drone/drone-01
[INFO] Companion setup complete
```

### 4.4 Companion (systemd — auto-start)

```bash
# Start / Stop
sudo systemctl start  drone-companion
sudo systemctl stop   drone-companion
sudo systemctl restart drone-companion

# Status
sudo systemctl status drone-companion

# Log realtime
journalctl -u drone-companion -f

# Log 100 dòng gần nhất
journalctl -u drone-companion -n 100
```

---

## 5. KIỂM TRA KẾT NỐI

### 5.1 Test MAVLink thủ công

```bash
python3 -c "
from pymavlink import mavutil
conn = mavutil.mavlink_connection('/dev/ttyAMA0', baud=57600)
print('Waiting for heartbeat...')
conn.wait_heartbeat(timeout=30)
print('PX4 connected — system:', conn.target_system, 'component:', conn.target_component)
"
```

### 5.2 Test WebSocket thủ công

```bash
python3 -c "
import asyncio, websockets

async def test():
    url = 'ws://192.168.137.1:8000/ws/drone/drone-01'
    async with websockets.connect(url) as ws:
        print('Connected:', url)

asyncio.run(test())
"
```

### 5.3 Test network connectivity

```bash
# Từ Pi → ping Backend
ping -c 4 192.168.137.1

# Từ Laptop → ping Pi
ping -c 4 192.168.137.139

# Kiểm tra port 8000 từ Pi
curl http://192.168.137.1:8000/health
```

---

## 6. LUỒNG MISSION

```
IDLE → ARMING → TAKEOFF → FLY_TO_PICKUP → DESCEND
     → SEARCH_ARUCO → PRECISION_LANDING
     → WAIT_PICKUP_CONFIRM
     → ARMING → TAKEOFF → FLY_TO_DROP → DESCEND
     → SEARCH_ARUCO → PRECISION_LANDING
     → WAIT_DROP_CONFIRM
     → ARMING → RETURN_HOME → IDLE
```

| Trạng thái | Mô tả | Trigger |
|-----------|-------|---------|
| `IDLE` | Chờ lệnh | - |
| `ARMING` | Gửi ARM, chờ PX4 confirm | START_MISSION |
| `TAKEOFF` | Cất cánh lên TAKEOFF_ALTITUDE_M | armed=True |
| `FLY_TO_PICKUP` | Bay đến pickup GPS | altitude OK |
| `DESCEND` | Hạ xuống DESCEND_ALTITUDE_M | reached pickup |
| `SEARCH_ARUCO` | Camera tìm ArUco marker | altitude OK |
| `PRECISION_LANDING` | Hạ cánh chính xác | marker detected |
| `WAIT_PICKUP_CONFIRM` | Chờ người xác nhận | landed |
| `RETURN_HOME` | RTL về Home | DROP_COMPLETE |

---

## 7. TROUBLESHOOTING

### 7.1 Không nhận MAVLink / Timeout

**Triệu chứng:**
```
[WARNING] MAVLink connection failed (attempt 1) — retrying in 5s
```

**Kiểm tra:**
```bash
# 1. Kiểm tra device tồn tại
ls -la /dev/ttyAMA0

# 2. Kiểm tra quyền (cần nhóm dialout)
groups rpi5
# → rpi5 adm dialout sudo ...
# Nếu thiếu dialout: sudo usermod -aG dialout rpi5  (rồi logout/login lại)

# 3. Kiểm tra UART enabled
cat /boot/firmware/config.txt | grep uart

# 4. Test trực tiếp pymavlink
python3 -c "
from pymavlink import mavutil
conn = mavutil.mavlink_connection('/dev/ttyAMA0', baud=57600)
conn.wait_heartbeat(timeout=15)
print('OK')
"
```

**Giải pháp:**
- Kiểm tra wiring TELEM1 ↔ Pi (TX↔RX phải chéo)
- Kiểm tra baudrate khớp trong QGroundControl (`SER_TEL1_BAUD = 57600`)
- Enable UART: `sudo raspi-config` → Interface → Serial
- Thêm `enable_uart=1` vào `/boot/firmware/config.txt`
- Thêm `dtoverlay=disable-bt` nếu `/dev/ttyAMA0` đang dùng cho Bluetooth

---

### 7.2 Không nhận PX4 Heartbeat

**Triệu chứng:** MAVLink connect thành công nhưng `wait_heartbeat()` timeout

**Kiểm tra:**
- PX4 đã boot chưa? LED Pixhawk nhấp nháy đúng pattern?
- Baudrare khớp: QGroundControl → Parameters → `SER_TEL1_BAUD = 57600`
- MAVLink protocol: `MAV_1_CONFIG = TELEM1`, `MAV_1_RATE = 0`
- Dây TX/RX có đúng chiều không?

---

### 7.3 WebSocket không kết nối

**Triệu chứng:**
```
[WARNING] WebSocket connect failed (attempt 1): ... — retrying in 3s
```

**Kiểm tra:**
```bash
# 1. Backend có đang chạy không?
curl http://192.168.137.1:8000/health

# 2. Đúng IP trong .env?
cat /opt/drone-delivery-system/companion/.env | grep SERVER_IP

# 3. Firewall trên Laptop
# Windows: Allow port 8000 inbound
# Linux: sudo ufw allow 8000

# 4. Ping connectivity
ping -c 4 192.168.137.1
```

---

### 7.4 Sai UART device

**Kiểm tra tất cả serial device:**
```bash
ls /dev/tty*
# GPIO UART:   /dev/ttyAMA0  (sau khi disable Bluetooth)
# USB Serial:  /dev/ttyUSB0, /dev/ttyACM0

# Xem chi tiết
dmesg | grep tty
```

**Cập nhật .env:**
```bash
# Nếu dùng USB-Serial adapter:
MAVLINK_DEVICE=/dev/ttyUSB0

# Nếu dùng GPIO UART (khuyên dùng):
MAVLINK_DEVICE=/dev/ttyAMA0
```

---

### 7.5 Sai IP / Không ping được

```bash
# Kiểm tra IP của Pi
hostname -I

# Cấu hình static IP (Pi 5 dùng NetworkManager, không phải dhcpcd)
sudo nmcli con mod "$(nmcli -t -f NAME con show --active | head -1)" \
    ipv4.addresses 192.168.137.139/24 \
    ipv4.gateway 192.168.137.1 \
    ipv4.method manual
sudo nmcli con up "$(nmcli -t -f NAME con show --active | head -1)"
```

---

### 7.6 Log file không tạo được

```bash
# Tạo và cấp quyền log file
sudo touch /var/log/drone-companion.log
sudo chown rpi5:rpi5 /var/log/drone-companion.log

# Hoặc đổi LOG_FILE thành local path trong .env:
LOG_FILE=/home/rpi5/drone-companion.log
```

---

## 8. UPDATE CODE TRÊN PI

```bash
# Từ VS Code Remote SSH terminal hoặc SSH thông thường:
cd /opt/drone-delivery-system
git pull

# Restart service
sudo systemctl restart drone-companion
journalctl -u drone-companion -f
```

---

## 9. PRE-FLIGHT CHECKLIST

- [ ] Backend `192.168.137.1:8000` → `curl http://192.168.137.1:8000/health` OK
- [ ] Pi `192.168.137.139` — ping từ Laptop OK
- [ ] SSH vào Pi thành công (rpi5@192.168.137.139)
- [ ] `.env` đã cấu hình đúng `SERVER_IP`, `MAVLINK_DEVICE`
- [ ] `python main.py` → PX4 heartbeat received
- [ ] WebSocket connected trong log
- [ ] Dashboard frontend hiển thị telemetry sau 2 giây
- [ ] GPS fix ≥ 6 satellites (trong dashboard)
- [ ] Battery > 50%
- [ ] ArUco marker đặt đúng vị trí pickup và drop
- [ ] Test FORCE RTL trước khi bay thật
- [ ] Khu vực bay clear (không người, không vật cản)

---

## 10. CẬP NHẬT GẦN ĐÂY

### 2026-07-16 — Camera Test + ArUco Detection (Full Stack)

- ✅ Companion: `CameraService` — mở USB camera headless, ArUco detection background thread
- ✅ Companion: Gửi `camera_status` (ON/OFF/ERROR) và `aruco_detection` qua WebSocket mỗi 2s
- ✅ Companion: Xử lý command `CAMERA_START` / `CAMERA_STOP` từ frontend
- ✅ Backend: `POST /camera/start`, `POST /camera/stop` endpoints
- ✅ Backend: Forward `camera_status` + `aruco_detection` tới frontend clients
- ✅ Frontend: `CameraPanel` — nút Test Camera, badge ON/OFF/ERROR, bảng ArUco info
- ✅ Frontend: WebSocket hook nhận `camera_status` + `aruco_detection` realtime
- ✅ RUNBOOK: Cập nhật lệnh PowerShell cho Windows, thêm hướng dẫn test camera

### 2026-07-14 — Chuyển sang Raspberry Pi 5 thực tế

- ✅ Xóa toàn bộ PC simulation / Windows COM port
- ✅ Config đọc từ environment variables (`.env` file)
- ✅ Main startup log: hostname, IP, MAVLink, WebSocket, mission state
- ✅ MAVLink auto-reconnect (retry vô hạn, không exit)
- ✅ WebSocket log chi tiết (URL, attempt number, delay)
- ✅ Tạo systemd service `drone-companion.service`
- ✅ Tạo `install_service.sh` — cài tự động 1 lần
- ✅ Cập nhật tài liệu cho headless Pi + VS Code SSH workflow

### 2026-07-13 — FSM & Mission Flow

- ✅ PX4 Auto-Disarm Integration
- ✅ WAIT_PICKUP_CONFIRM / WAIT_DROP_CONFIRM gates
- ✅ Continuous Delivery Mode (intercept trong RETURN_HOME)
- ✅ Database: PostgreSQL → SQLite
