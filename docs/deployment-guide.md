# Hướng dẫn Triển khai (Deployment Guide)

Tài liệu này hướng dẫn chi tiết cách triển khai hệ thống Drone Delivery từ phần cứng, mạng LAN, cấu hình Raspberry Pi, cho đến việc khởi chạy các dịch vụ Backend, Frontend và Companion.

---

## 1. Network Topology (Mạng LAN nội bộ)

Hệ thống hoạt động trên một mạng LAN nội bộ cô lập (không cần Internet).

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

### Static IP Assignments
| Thiết bị | IP | Ghi chú |
|----------|----|---------|
| Backend Server (Laptop) | `192.168.137.1` | Gateway/Server IP |
| Raspberry Pi 5 | `192.168.137.139` | Allocated via Hotspot DHCP |

---

## 2. Cài đặt Raspberry Pi 5 (Headless)

### 2.1 Yêu cầu phần cứng
- Raspberry Pi 5 (4GB hoặc 8GB)
- MicroSD ≥ 32GB (Class 10 / A2)
- Nguồn USB-C 5V/5A
- Dây kết nối UART & CSI Camera

### 2.2 Flash OS & Thiết lập cơ bản
1. Dùng **Raspberry Pi Imager**, chọn OS **Raspberry Pi OS Lite (64-bit)**.
2. Edit Settings trước khi flash:
   - Hostname: `raspberrypi`
   - Username/Password: `rpi5` / `[mật khẩu]`
   - WiFi SSID/Password: `[Tên Hotspot]` / `[Pass Hotspot]`
   - Bật SSH bằng mật khẩu.

### 2.3 Kết nối SSH và Set Static IP
Sau khi Pi khởi động (~1-2 phút):
```bash
ssh rpi5@192.168.137.139
```

**Set Static IP (NetworkManager):**
```bash
sudo nmcli con mod "preconfigured" \
    ipv4.addresses 192.168.137.139/24 \
    ipv4.gateway   192.168.137.1 \
    ipv4.dns       192.168.137.1 \
    ipv4.method    manual
sudo nmcli con up "preconfigured"
```

### 2.4 Kích hoạt UART & Nhóm quyền
Tắt Bluetooth để giải phóng `/dev/ttyAMA0` cho MAVLink:
```bash
sudo nano /boot/firmware/config.txt
# Thêm vào cuối file:
enable_uart=1
dtoverlay=disable-bt
```

Thêm user vào nhóm `dialout`:
```bash
sudo usermod -aG dialout rpi5
sudo reboot
```

---

## 3. Cài đặt Môi trường Phát triển (VS Code Remote SSH)

Để dev trực tiếp trên Pi:
1. Cài extension **Remote - SSH** trên VS Code.
2. Nhấn `Ctrl+Shift+P` → `Remote-SSH: Connect to Host` → `rpi5@192.168.137.139`.
3. VS Code Server sẽ tự cài đặt trên Pi.
4. Mở folder `/opt/drone-delivery-system` để làm việc.

---

## 4. Triển khai Hệ thống

### 4.1 Backend (Trên Laptop - 192.168.137.1)
Yêu cầu Python 3.11+.

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Kiểm tra: `curl http://192.168.137.1:8000/health`

### 4.2 Frontend - Admin & Customer (Trên Laptop)
Mở 2 terminal riêng biệt:

**Admin Dashboard (Port 5173):**
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

**Customer Frontend (Port 5174):**
```bash
cd customer-frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5174
```

### 4.3 Companion App (Trên Raspberry Pi - 192.168.137.139)
Clone code và cài đặt:
```bash
sudo mkdir -p /opt/drone-delivery-system
sudo chown rpi5:rpi5 /opt/drone-delivery-system
git clone https://github.com/padungaz/drone-delivery-system.git /opt/drone-delivery-system
cd /opt/drone-delivery-system/companion

# Chạy script cài đặt tự động (cài requirements, service, .env)
chmod +x install_service.sh
sudo ./install_service.sh
```

Kiểm tra nội dung `.env` (`nano /opt/drone-delivery-system/companion/.env`):
```bash
SERVER_IP=192.168.137.1
SERVER_PORT=8000
DRONE_ID=drone-01
MAVLINK_DEVICE=/dev/ttyAMA0
MAVLINK_BAUD=921600
LOG_FILE=/var/log/drone-companion.log
LOG_LEVEL=INFO
```

**Chạy Service:**
```bash
sudo systemctl start drone-companion
journalctl -u drone-companion -f
```

---

## 5. Cài đặt Camera (Tùy chọn)
Để dùng tính năng hạ cánh ArUco, Pi cần cài đặt thư viện camera:
```bash
sudo apt install -y python3-picamera2
```
