# RUNBOOK — Vận hành & Gỡ lỗi (Smart Intralogistics & Drone Delivery v3.0)

Tài liệu này tập trung vào các thao tác vận hành hàng ngày (Operations), kiểm tra thử nghiệm tự động, kiểm tra lỗi (Troubleshooting), và danh sách kiểm tra an toàn hệ thống Kho thông minh & Drone.

---

## 1. Pre-Flight & Pre-Operation Checklist

Trước khi vận hành thử nghiệm hoặc bay tự động, bắt buộc hoàn thành kiểm tra:

### 1.1. Hệ thống Kho thông minh (Smart Intralogistics)
- [ ] **Backend Server:** Centralized FastAPI App đang chạy (`http://localhost:8000/docs` hiển thị v3.0 OK).
- [ ] **Thiết bị phần cứng LAN:** Đã kết nối mạng LAN cho UAV (`192.168.1.20`), PLC S7-1200 (`192.168.1.30`), FAIRINO Robot (`192.168.1.40`), Camera (`192.168.1.50`).
- [ ] **Trạm hạ cánh PLC:** Cảm biến chân tiếp đất nhận diện chính xác, kẹp cơ khí X/Y không bị vướng vật cản.
- [ ] **Trục Nâng Z:** Động cơ trục Z chuyển động trơn tru giữa vị trí HOME, UP, DOWN.
- [ ] **Cánh tay Robot FAIRINO:** Trạng thái READY, không phát sinh lỗi va chạm, tọa độ gốc HOME chính xác.
- [ ] **Ô chứa hàng 3x3:** Ma trận ô A1..C3 hiển thị đúng trạng thái trên giao diện Admin Dashboard.

### 1.2. Chuyến bay Drone (UAV)
- [ ] **Kết nối Raspberry Pi 5:** Ping `192.168.1.20` / `192.168.137.139` thành công.
- [ ] **Companion Service:** Tiến trình `drone-companion` hoạt động ổn định.
- [ ] **Pixhawk MAVLink:** Nhận tín hiệu Heartbeat từ PX4 6C qua MAVLink UART.
- [ ] **Định vị & Pin:** GPS Fix ≥ 6 vệ tinh, Pin > 50%.
- [ ] **ArUco Landing:** Đã đặt mã ArUco tại vị trí landing pad và vị trí nhận/giao hàng.

---

## 2. Kiểm tra Tự động & Test Scripts (Integration Testing)

Hệ thống cung cấp kịch bản kiểm thử tích hợp tự động cho toàn bộ luồng đa thiết bị (UAV + PLC + FAIRINO Robot + Storage):

### 2.1. Chạy Integration Test tự động (Smart Intralogistics)
Chạy tập lệnh kiểm thử tích hợp trên máy Backend:

```bash
cd backend
.\venv\Scripts\python.exe test_smart_intralogistics.py
```

**Kịch bản kiểm thử tự động thực hiện 8 bước:**
1. Khởi tạo Cơ sở Dữ liệu & Bảng lưu trữ.
2. Đăng ký 4 thiết bị LAN: `UAV01`, `PLC01`, `ROBOT01`, `CAM01`.
3. Khởi tạo 9 ô kho thông minh (`A1` đến `C3`).
4. Mô phỏng quét mã QR `SP001` từ Camera -> Tự động gán ô phù hợp.
5. Kiểm tra các lệnh PLC Docking (`LOCK_DRONE`, `Z_UP`, `UNLOCK_DRONE`).
6. Kiểm tra các lệnh Cánh tay Robot FAIRINO (`MOVE_HOME`, `PICK`, `STORE`).
7. Khởi chạy FSM **Flow 8: DRONE_PICKUP** (Nhập kho tự động khi Drone mang hàng về).
8. Khởi chạy FSM **Flow 9: DRONE_DELIVERY** (Xuất kho tự động từ ô lưu trữ lên Drone).

---

## 3. Kiểm tra Kết nối Thủ công (Manual Verification)

### 3.1. Test WebSocket System Hub (`/ws/system`)
Chạy script kiểm tra WebSocket broadcast:
```python
import asyncio, websockets, json

async def test_system_ws():
    url = 'ws://localhost:8000/ws/system'
    async with websockets.connect(url) as ws:
        print('Connected to System WebSocket!')
        while True:
            msg = await ws.recv()
            print('Broadcast Event:', json.loads(msg))

asyncio.run(test_system_ws())
```

### 3.2. Test API Trạng thái Thiết bị LAN
```bash
# Lấy danh sách thiết bị LAN
curl http://localhost:8000/api/v1/devices

# Kiểm tra trạng thái PLC S7-1200
curl http://localhost:8000/api/v1/plc/status

# Kiểm tra trạng thái Robot FAIRINO
curl http://localhost:8000/api/v1/robot/status

# Lấy trạng thái ô lưu trữ 3x3
curl http://localhost:8000/api/v1/inventory/slots
```

---

## 4. Quản lý Tiến trình trên Raspberry Pi 5

```bash
# Khởi động / Dừng / Khởi động lại service companion
sudo systemctl start drone-companion
sudo systemctl stop drone-companion
sudo systemctl restart drone-companion

# Xem log thời gian thực
journalctl -u drone-companion -f
```

---

## 5. Xử lý Sự cố (Troubleshooting)

### 5.1. PLC báo trạng thái Timeout hoặc Không nhận Lệnh Kẹp
- **Triệu chứng:** Giao diện báo `PLC: Offline` hoặc lệnh `LOCK_DRONE` bị ngưng trệ.
- **Khắc phục:**
  - Kiểm tra kết nối mạng LAN tới IP của PLC Siemens S7-1200 (`192.168.1.30`).
  - Đảm bảo Backend đang chạy ở chế độ Simulator (`simulator_mode=True`) nếu chưa nối phần cứng thật.
  - Kiểm tra công tắc hành trình cảm biến tiếp đất của sàn nâng.

### 5.2. Cánh tay Robot FAIRINO dừng giữa chừng (State: ERROR)
- **Triệu chứng:** Robot dừng chuyển động và báo trạng thái ERROR trên Dashboard.
- **Khắc phục:**
  - Kiểm tra xem nút Emergency Stop trên tủ điều khiển Robot có bị nhấn không.
  - Gửi lệnh `MOVE_HOME` qua REST API hoặc nút nhấn trên Admin Dashboard để reset vị trí Robot:
    ```bash
    curl -X POST http://localhost:8000/api/v1/robot/command -H "Content-Type: application/json" -d "{\"command\": \"MOVE_HOME\"}"
    ```

### 5.3. Ô lưu trữ hiển thị sai thông tin mặt hàng
- **Khắc phục:** Mở tab **Kho thông minh (Intralogistics)** trên Admin Dashboard, chọn ô bị lỗi, nhấn nút "Reset / Clear Slot" để đưa ô về trạng thái `EMPTY`.

### 5.4. Lỗi Mất kết nối MAVLink với Pixhawk 6C
- **Khắc phục:**
  - Kiểm tra cáp nối UART (TX ↔ RX).
  - Kiểm tra baudrate trong PX4 parameter: `SER_TEL2_BAUD = 921600`.
  - Kiểm tra quyền truy cập tệp cổng nối tiếp: `sudo usermod -aG dialout rpi5`.
