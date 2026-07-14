# Drone Delivery Autonomous System

Hệ thống drone giao hàng tự động chạy hoàn toàn trên mạng LAN nội bộ.

## Kiến trúc hệ thống

```
Client App (React)  ──HTTP/WS──►  FastAPI Backend (192.168.137.1:8000)
                                         │
                                    WebSocket
                                         │
                               Raspberry Pi 5 (192.168.137.139)
                                         │
                                  MAVLink UART
                                  (/dev/ttyAMA0)
                                         │
                               Pixhawk 6C (PX4 Firmware)
```

## Hardware Setup

| Component | Model | Kết nối |
|-----------|-------|---------|
| Companion Computer | Raspberry Pi 5 (4GB/8GB) | LAN WiFi |
| Flight Controller | Pixhawk 6C | UART GPIO (`/dev/ttyAMA0`) |
| Firmware | PX4 | MAVLink 1/2 |
| Camera | CSI Camera Module | CSI port |
| Rangefinder | MTF-02P | I2C / Serial |

### MAVLink Wiring (Pixhawk TELEM1 ↔ Pi GPIO UART)

```
Pixhawk TELEM1          Raspberry Pi 5
─────────────           ──────────────
  TX  (pin 2)  ──────►  GPIO15 / RXD  (pin 10)
  RX  (pin 3)  ◄──────  GPIO14 / TXD  (pin 8)
  GND (pin 6)  ────────  GND          (pin 6)
  5V  (pin 1)  ──────►  5V Power      (optional)
```

## Development Environment

### Headless Raspberry Pi

Raspberry Pi 5 chạy headless (không màn hình, bàn phím, chuột).
Toàn bộ development qua **VS Code Remote SSH** từ Laptop:

```
Laptop/PC Developer
      │
      │  VS Code Remote SSH (SSH over LAN/WiFi Hotspot)
      ▼
Raspberry Pi 5 (192.168.137.139)
      │
      │  MAVLink UART
      ▼
Pixhawk 6C (PX4)
```

### Kết nối SSH

```bash
ssh rpi5@192.168.137.139
```

VS Code: `Remote SSH` → `Connect to Host` → `rpi5@192.168.137.139`

## Cấu trúc Monorepo

| Thư mục | Mô tả |
|---------|-------|
| `backend/` | FastAPI server, WebSocket hub, SQLite database |
| `frontend/` | React + TypeScript control dashboard |
| `companion/` | Raspberry Pi mission manager, MAVLink, ArUco vision |
| `docs/` | PX4 parameters, LAN deployment guide, Pi setup guide |

## Quick Start

### Backend (Laptop/PC — 192.168.2.28)

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Companion (Raspberry Pi 5 — 192.168.137.139)

SSH vào Raspberry Pi:

```bash
ssh rpi5@192.168.137.139
cd /opt/drone-delivery-system/companion

# Cài lần đầu
cp .env.example .env
nano .env                          # Sửa SERVER_IP, MAVLINK_DEVICE

# Chạy thủ công
source venv/bin/activate
python main.py

# Hoặc chạy qua systemd service
sudo systemctl start drone-companion
journalctl -u drone-companion -f   # Xem log realtime
```

## Network Configuration

| Device | IP | Port |
|--------|-----|------|
| Backend Server (Laptop Hotspot) | `192.168.137.1` | `8000` |
| Raspberry Pi 5 | `192.168.137.139` | — |
| React Frontend | `192.168.137.1` | `5173` |
| WebSocket | `ws://192.168.137.1:8000/ws/drone/drone-01` | — |

## Environment Variables (companion/.env)

```bash
SERVER_IP=192.168.137.1          # IP Hotspot của Laptop/PC
SERVER_PORT=8000
DRONE_ID=drone-01
MAVLINK_DEVICE=/dev/ttyAMA0     # hoặc /dev/ttyUSB0
MAVLINK_BAUD=57600
LOG_FILE=/var/log/drone-companion.log
LOG_LEVEL=INFO
```

## Tài liệu

- [Raspberry Pi 5 Setup Guide](docs/raspberry-pi-setup.md)
- [LAN Deployment Guide](docs/lan-deployment-guide.md)
- [PX4 Parameter Configuration](docs/px4-parameters.md)
- [RUNBOOK — Vận hành & Debug](RUNBOOK.md)
