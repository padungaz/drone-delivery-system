# Raspberry Pi 5 Setup Guide

Hướng dẫn cài đặt đầy đủ Raspberry Pi 5 headless cho Drone Delivery companion computer.

---

## 1. Yêu cầu phần cứng

| Component | Ghi chú |
|-----------|---------|
| Raspberry Pi 5 (4GB hoặc 8GB) | Board chính |
| MicroSD ≥ 32GB (Class 10 / A2) | Khuyến dùng SanDisk Extreme |
| USB-C 5V/5A Power Supply | Nguồn ổn định, tránh voltage drop |
| Pixhawk 6C | Kết nối UART |
| Dây nối GPIO UART (JST-GH) | Pixhawk TELEM1 ↔ Pi GPIO |
| CSI Camera Module | Tùy chọn — cho ArUco landing |
| WiFi Router (DroneLAN) | Cùng mạng LAN |

---

## 2. Cài Raspberry Pi OS

### 2.1 Download Raspberry Pi Imager

Tải tại: https://www.raspberrypi.com/software/

Chọn:
- **Device**: Raspberry Pi 5
- **OS**: Raspberry Pi OS Lite (64-bit) — không cần Desktop
- **Storage**: MicroSD card

### 2.2 Configure OS Settings (Headless)

Trước khi flash, nhấn ⚙️ **Edit Settings**:

```
Hostname:        raspberrypi
Username:        rpi5
Password:        [đặt mật khẩu mạnh]

WiFi SSID:       [Tên Hotspot từ Laptop]
WiFi Password:   [Mật khẩu Hotspot]
WiFi Country:    VN

Enable SSH:      ✅ Use password authentication
```

Flash vào MicroSD → Insert vào Pi → Power on.

---

## 3. Kết nối SSH lần đầu

```bash
# Từ Laptop (sau khi Pi boot ~1-2 phút)
ssh rpi5@raspberrypi.local
# Hoặc dùng IP trực tiếp từ Hotspot:
ssh rpi5@192.168.137.139

# Kiểm tra IP của Pi (trên hotspot DHCP lease)
# hoặc dùng nmap:
nmap -sn 192.168.137.0/24 | grep -A1 "Raspberry"
```

---

## 4. Cấu hình hệ thống Pi

### 4.1 Update OS

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget nano python3-pip python3-venv
```

### 4.2 Set Static IP (NetworkManager — Pi 5 Bookworm)

```bash
# Xem tên WiFi connection
nmcli con show

# Set static IP (ví dụ nếu muốn đặt cố định IP 192.168.137.139)
sudo nmcli con mod "preconfigured" \
    ipv4.addresses 192.168.137.139/24 \
    ipv4.gateway   192.168.137.1 \
    ipv4.dns       192.168.137.1 \
    ipv4.method    manual

sudo nmcli con up "preconfigured"

# Verify
hostname -I
# 192.168.137.139
```

> ⚠️ **Quan trọng:** Raspberry Pi 5 (Bookworm) dùng **NetworkManager**, không phải `dhcpcd`. Đừng dùng `/etc/dhcpcd.conf`.

### 4.3 Enable UART (tắt Bluetooth để /dev/ttyAMA0 free)

```bash
sudo raspi-config
```
Chọn: `Interface Options` → `Serial Port`
- "Would you like a login shell accessible over serial?" → **No**
- "Would you like the serial port hardware to be enabled?" → **Yes**

Hoặc edit trực tiếp:
```bash
sudo nano /boot/firmware/config.txt
```

Thêm vào cuối file:
```
# Enable UART, disable Bluetooth serial
enable_uart=1
dtoverlay=disable-bt
```

```bash
sudo reboot
```

Sau khi reboot:
```bash
# Kiểm tra UART
ls -la /dev/ttyAMA*
# crw-rw---- 1 root dialout ... /dev/ttyAMA0

# Kiểm tra không có process khác dùng
sudo fuser /dev/ttyAMA0
```

### 4.4 Thêm pi vào nhóm dialout (UART access)

```bash
sudo usermod -aG dialout rpi5

# Logout và login lại để có hiệu lực
exit
ssh rpi5@192.168.137.139

# Kiểm tra
groups
# rpi5 adm dialout sudo ...
```

### 4.5 Tắt swap (optional — tăng hiệu suất MicroSD)

```bash
sudo systemctl disable dphys-swapfile
sudo systemctl stop dphys-swapfile
```

---

## 5. Cài đặt VS Code Remote SSH

### 5.1 Trên Laptop (1 lần)

1. Cài **VS Code**: https://code.visualstudio.com/
2. Cài extension **Remote - SSH** (Microsoft)

### 5.2 Connect tới Pi

```
Ctrl+Shift+P → Remote-SSH: Connect to Host
Nhập: rpi5@192.168.137.139
Chọn OS: Linux
```

VS Code Server sẽ tự động cài trên Pi (~2-3 phút lần đầu).

### 5.3 SSH Key Authentication (không cần nhập password)

```bash
# Từ Laptop
ssh-keygen -t rsa -b 4096   # Nếu chưa có key
ssh-copy-id rpi5@192.168.137.139

# Test
ssh rpi5@192.168.137.139   # Không hỏi password
```

### 5.4 SSH Config (kết nối nhanh)

Thêm vào `~/.ssh/config` trên Laptop:
```
Host pi-drone
    HostName 192.168.137.139
    User rpi5
    IdentityFile ~/.ssh/id_rsa
    ServerAliveInterval 30
```

```bash
ssh pi-drone   # Shortcut
```

---

## 6. Deploy Drone Companion

### 6.1 Clone project lên Pi

```bash
# SSH vào Pi
ssh pi-drone

# Clone vào /opt
sudo mkdir -p /opt/drone-delivery-system
sudo chown rpi5:rpi5 /opt/drone-delivery-system
git clone https://github.com/padungaz/drone-delivery-system.git /opt/drone-delivery-system
```

### 6.2 Cài tự động qua install script

```bash
cd /opt/drone-delivery-system/companion
chmod +x install_service.sh
sudo ./install_service.sh
```

Script sẽ:
1. Copy files vào `/opt/drone-delivery-system/companion`
2. Tạo Python venv
3. Cài dependencies từ `requirements.txt`
4. Tạo `.env` từ `.env.example`
5. Cài systemd service
6. Add user vào dialout group

### 6.3 Cấu hình .env

```bash
nano /opt/drone-delivery-system/companion/.env
```

```bash
SERVER_IP=192.168.137.1      # IP laptop chạy hotspot
SERVER_PORT=8000
DRONE_ID=drone-01
MAVLINK_DEVICE=/dev/ttyAMA0
MAVLINK_BAUD=57600
LOG_FILE=/var/log/drone-companion.log
LOG_LEVEL=INFO
```

### 6.4 Tạo log file

```bash
sudo touch /var/log/drone-companion.log
sudo chown rpi5:rpi5 /var/log/drone-companion.log
```

---

## 7. Chạy Companion

### 7.1 Thủ công (test)

```bash
cd /opt/drone-delivery-system/companion
source venv/bin/activate
python main.py
```

Kết quả dự kiến:
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
[INFO] MAVLink connect attempt 1 → /dev/ttyAMA0 @ 57600 baud
[INFO] Waiting for PX4 heartbeat (timeout=30s)...
[INFO] PX4 heartbeat received — system=1 component=1
[INFO] WebSocket connecting to ws://192.168.137.1:8000/... (attempt 1)...
[INFO] WebSocket connected to ws://192.168.137.1:8000/ws/drone/drone-01
[INFO] Companion setup complete
```

### 7.2 Qua systemd (production)

```bash
sudo systemctl start  drone-companion
sudo systemctl status drone-companion
journalctl -u drone-companion -f    # Xem log realtime
```

---

## 8. (Tùy chọn) CSI Camera cho ArUco Landing

```bash
# Cài picamera2
sudo apt install -y python3-picamera2

# Hoặc uncommment trong requirements.txt:
# picamera2==0.3.25
# Rồi pip install lại

# Test camera
python3 -c "
from picamera2 import Picamera2
cam = Picamera2()
cam.start()
print('Camera OK')
cam.stop()
"
```

---

## 9. Kiểm tra MAVLink

```bash
# Test kết nối Pixhawk
python3 -c "
from pymavlink import mavutil
conn = mavutil.mavlink_connection('/dev/ttyAMA0', baud=57600)
print('Waiting for heartbeat...')
conn.wait_heartbeat(timeout=30)
print('System:', conn.target_system, 'Component:', conn.target_component)
"
```

---

## 10. Update Project

```bash
# SSH vào Pi hoặc dùng VS Code Remote SSH terminal
cd /opt/drone-delivery-system
git pull

# Restart companion
sudo systemctl restart drone-companion
journalctl -u drone-companion -f
```

---

## 11. Troubleshooting

| Vấn đề | Giải pháp |
|--------|---------|
| SSH không kết nối được | Kiểm tra IP, Pi đã boot chưa, cùng mạng WiFi? |
| `/dev/ttyAMA0` không có | Enable UART trong `raspi-config`, thêm `enable_uart=1` |
| Permission denied UART | `sudo usermod -aG dialout rpi5` + logout/login |
| Pi lấy IP khác | Set static IP qua `nmcli` (không dùng `dhcpcd`) |
| MAVLink timeout | Kiểm tra wiring TX↔RX chéo, baudrate PX4 = 57600 |
| WebSocket fail | Backend đang chạy? Ping `192.168.137.1`? Firewall? |
| Service không start | `journalctl -u drone-companion -n 50` để xem lỗi |
| Camera không open | `sudo apt install python3-picamera2`, kiểm tra CSI cable |
