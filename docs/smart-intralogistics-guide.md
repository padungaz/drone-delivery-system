# Hướng dẫn Hệ thống Kho Thông minh (Smart Intralogistics Controller System Guide)

Tài liệu này hướng dẫn chi tiết về kiến trúc, giao thức phần cứng, quy trình điều phối FSM tự động, giao diện điều khiển và kịch bản thử nghiệm cho hệ thống **Smart Intralogistics Controller System (v3.0)**.

---

## 1. Tổng quan Hệ thống

Hệ thống Kho Thông minh (Smart Intralogistics) là trung tâm điều phối tự động hóa nối liền vận chuyển tự động bằng Drone (UAV) và quy trình nhập/xuất/lưu kho tự động. Hệ thống hoạt động tập trung trên mạng LAN nội bộ, điều khiển đồng bộ 4 nhóm thiết bị chính:

1. **UAV Drone:** Drone tự bay nhận/giao hàng, hạ cánh chính xác bằng ArUco Marker.
2. **Trạm Hạ cánh PLC Siemens S7-1200:** Quản lý cảm biến tiếp đất, kẹp cơ khí khóa chân chân UAV (Clamp X/Y), và Trục Nâng Z.
3. **Cánh tay Robot FAIRINO (Cobot 6-DoF):** Thực hiện thao tác gắp/đặt hàng chính xác giữa UAV, Trục Nâng Z và Ma trận Ô chứa hàng.
4. **Ma trận Ô chứa hàng 3x3 (A1..C3 Grid):** 9 ô lưu trữ hàng hóa thông minh tự động quản lý vị trí sản phẩm và quét mã QR Vision.

---

## 2. Phần cứng & Giao thức Kết nối Mạng LAN

Toàn bộ các thiết bị giao tiếp với Central FastAPI Backend Server thông qua mạng LAN nội bộ với địa chỉ IP tĩnh hoặc dynamic DHCP:

| Thiết bị | Loại (DeviceType) | IP Mặc định | Giao thức | Chức năng chính |
|----------|-------------------|-------------|-----------|-----------------|
| **UAV01** | `UAV` | `192.168.1.20` | WebSocket / MAVLink | Máy bay không người lái giao/nhận hàng |
| **PLC01** | `PLC` | `192.168.1.30` | Snap7 / S7 Protocol / REST | Điều khiển Kẹp X/Y, Cảm biến Landing Pad, Trục Z |
| **ROBOT01** | `ROBOT` | `192.168.1.40` | TCP/IP Sockets / REST | Cánh tay Robot gắp/đặt sản phẩm (Slots A1..C3) |
| **CAM01** | `CAMERA` | `192.168.1.50` | RTSP Stream / REST API | Camera quét mã QR sản phẩm nhập kho |

---

## 3. Máy Trạng thái Điều phối Tự động (Master FSM Orchestrator)

Lớp dịch vụ `MissionManager` đóng vai trò là Orchestrator trung tâm điều hành máy trạng thái FSM liên kết giữa UAV, PLC, Robot và Inventory.

### 3.1. Quy trình Nhập kho tự động (Flow 8: DRONE_PICKUP)
Khi UAV mang hàng từ xa về trạm hạ cánh kho để cất hàng vào ô lưu trữ:

```
[1. UAV Touchdown] ──► [2. PLC Sensor Detect] ──► [3. PLC LOCK_DRONE (Clamps X/Y)]
                                                              │
[6. Robot Pick Product] ◄── [5. PLC Z_UP] ◄── [4. Robot MOVE_HOME]
         │
         ▼
[7. Robot Return HOME] ──► [8. PLC Z_DOWN] ──► [9. Inventory Find Free Slot (A1..C3)]
                                                              │
[11. PLC UNLOCK_DRONE] ◄── [10. Robot STORE_PRODUCT into Slot] ◄──┘
```

**Các bước chi tiết:**
1. **Khởi tạo:** Server nhận lệnh `POST /api/v1/missions/drone-pickup`, tạo bản ghi mission trạng thái `STARTED`.
2. **Tiếp đất:** UAV hạ cánh xuống sàn hạ cánh. Cảm biến PLC nhận diện `drone_detected = True`.
3. **Khóa Drone:** PLC kích hoạt xilanh kẹp cơ khí X và Y (`LOCK_DRONE`), giữ cố định chân Drone.
4. **Robot chuẩn bị:** Robot FAIRINO di chuyển về vị trí an toàn (`MOVE_HOME`).
5. **Nâng trục Z:** PLC nâng bàn nâng Z lên độ cao tiếp cận (`Z_UP`).
6. **Gắp hàng:** Robot FAIRINO gắp sản phẩm khỏi gá chứa hàng của UAV (`PICK_PRODUCT`).
7. **Rút về an toàn:** Robot rút về vị trí `HOME` và yêu cầu hạ bàn nâng Z (`Z_DOWN`).
8. **Tìm ô trống:** `InventoryManager` duyệt 9 ô chứa hàng, chọn ô có trạng thái `EMPTY`.
9. **Cất hàng vào ô:** Robot di chuyển cất sản phẩm vào ô được chỉ định (Ví dụ: `B2`) và chuyển trạng thái ô sang `OCCUPIED`.
10. **Mở kẹp:** PLC mở kẹp khóa (`UNLOCK_DRONE`), sẵn sàng cho UAV cất cánh quay về.

---

### 3.2. Quy trình Xuất kho lên Drone (Flow 9: DRONE_DELIVERY)
Khi có đơn hàng cần giao, Robot lấy hàng từ ô chứa đặt lên Drone để cất cánh giao hàng:

```
[1. Order Request] ──► [2. Inventory Find Product Slot] ──► [3. Robot PICK from Slot]
                                                                  │
[6. PLC Z_UP & Robot PLACE on UAV] ◄── [5. PLC LOCK_DRONE] ◄── [4. UAV Landed on Pad]
         │
         ▼
[7. Robot Return HOME & PLC Z_DOWN] ──► [8. PLC UNLOCK_DRONE] ──► [9. UAV Takeoff Cleared]
```

**Các bước chi tiết:**
1. **Xác định vị trí:** Tìm sản phẩm `product_id` trong danh sách ô lưu trữ (A1..C3).
2. **Lấy hàng:** Robot gắp hàng từ ô lưu trữ, cập nhật trạng thái ô về `EMPTY`.
3. **Tiếp đất & Khóa:** UAV tiếp đất sàn nâng, PLC kích hoạt kẹp `LOCK_DRONE`.
4. **Nâng Z & Đặt hàng:** PLC nâng bàn nâng Z (`Z_UP`), Robot đặt sản phẩm lên gá chứa hàng của UAV.
5. **Hạ Z & Trở về:** PLC hạ bàn nâng Z (`Z_DOWN`), Robot trở về gốc `HOME`.
6. **Giải phóng UAV:** PLC mở kẹp `UNLOCK_DRONE` và cấp phép cất cánh cho UAV hoàn thành chuyến bay giao hàng.

---

## 4. Cấu trúc Giao diện Admin Dashboard (Frontend)

Giao diện Quản trị viên (React + TypeScript) được thiết kế hiện đại với 4 tab điều khiển:

1. 🏭 **Kho thông minh (Intralogistics Panel):**
   - **Bảng Trạng thái Thiết bị LAN:** Theo dõi nhịp tim (Heartbeat), IP, và trạng thái ONLINE/OFFLINE của UAV, PLC, Robot, Camera.
   - **Bảng Điều khiển PLC S7-1200:** Hiển thị thời gian thực các cảm biến tiếp đất, trạng thái kẹp X/Y, vị trí nâng Z, công tắc E-Stop và các nút điều khiển thủ công (`Lock Drone`, `Unlock Drone`, `Z Up`, `Z Down`).
   - **Bảng Điều khiển Robot FAIRINO:** Hiển thị tọa độ không gian Cartesian (X, Y, Z, Rx, Ry, Rz), góc khớp Joint (J1..J6), sản phẩm đang cầm, và các thao tác thủ công (`Move Home`, `Pick`, `Place`).
   - **Lưới Ô Chứa Hàng 3x3 (Storage Grid A1..C3):** Ma trận 9 ô lưu trữ hiển thị màu sắc theo trạng thái (Xanh lá = EMPTY, Xanh dương = OCCUPIED, Cam = RESERVED). Tích hợp bộ giả lập quét mã QR Vision.
2. 📊 **Bảng điều khiển Drone:** Theo dõi góc nghiêng Roll/Pitch/Yaw, độ cao, tốc độ, dung lượng pin và form điều khiển chuyến bay.
3. 🗺️ **Bản đồ Live Map:** Bản đồ trực quan hiển thị đường bay GPS của Drone thời gian thực.
4. 🧩 **Chế độ Song song (Split View):** Kết hợp đồng thời Live Map, Telemetry, Cấu hình kho và Camera nhận diện ArUco.

---

## 5. Hướng dẫn Chạy Kiểm thử & Khởi chạy

### 5.1. Khởi chạy Backend Server
```bash
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5.2. Khởi chạy Integration Test cho Kho thông minh
Tập lệnh thử nghiệm độc lập xác minh toàn bộ các API và máy trạng thái FSM:
```bash
cd backend
.\venv\Scripts\python.exe test_smart_intralogistics.py
```

### 5.3. Khởi chạy Frontend Dashboard
```bash
cd frontend
npm run dev -- --host 0.0.0.0
```
Mở trình duyệt truy cập `http://localhost:5173`, chọn tab **🏭 Kho thông minh (Intralogistics)** để vận hành.
