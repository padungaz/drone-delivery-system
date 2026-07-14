# Drone Delivery Autonomous System

Hệ thống drone giao hàng tự động chạy hoàn toàn trên mạng LAN nội bộ.

## Kiến trúc

```
Client App (React)  ──HTTP/WS──►  FastAPI Backend (192.168.2.28:8000)
                                        │
                                   WebSocket
                                        │
                              Raspberry Pi 5 (192.168.2.100)
                                        │
                                   MAVLink UART
                                        │
                              Pixhawk 6C (PX4)
```

## Cấu trúc Monorepo

| Thư mục | Mô tả |
|---------|-------|
| `backend/` | FastAPI server, WebSocket hub, SQLite database |
| `frontend/` | React + TypeScript control dashboard |
| `companion/` | Raspberry Pi mission manager, MAVLink, ArUco vision |
| `docs/` | PX4 parameters, LAN deployment guide |

## Quick Start

### Backend (192.168.2.28)

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Companion (Raspberry Pi / simulation)

For PC simulation, keep `companion/config.py` set to `RUN_MODE = "sim"` and install dependencies without `picamera2`.
On Raspberry Pi, switch `RUN_MODE = "pi"` and uncomment `picamera2==0.3.25` in `companion/requirements.txt`.

```bash
cd companion
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Network

- SSID: `DroneLAN`
- Subnet: `192.168.2.0/24`
- Backend: `192.168.2.28:8000`
- Raspberry Pi: `192.168.2.100`
- WebSocket: `ws://192.168.2.28:8000/ws/drone`

## Tài liệu

- [PX4 Parameter Configuration](docs/px4-parameters.md)
- [LAN Deployment Guide](docs/lan-deployment-guide.md)
