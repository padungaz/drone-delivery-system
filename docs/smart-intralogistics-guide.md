# Hướng dẫn Hệ thống Kho Thông minh (Smart Intralogistics Controller System Guide)

Tài liệu này hướng dẫn chi tiết về kiến trúc 4 tầng Decoupled mới, giao thức phần cứng PLC DB15, quy trình điều phối tự động, giao diện điều khiển và kịch bản thử nghiệm cho hệ thống **Smart Intralogistics Controller System (v3.0)**.

---

## 1. Tổng quan Kiến trúc 4 Tầng Decoupled (Decoupled 4-Layer Architecture)

Hệ thống Kho Thông minh (Smart Intralogistics) được thiết kế lại theo chuẩn **4 Tầng Phân Tách Độc Lập (Decoupled Layers)**, loại bỏ việc trộn lẫn logic giữa Đơn hàng, Nhiệm vụ và Lệnh thiết bị:

```
===================================================================================
1. CUSTOMER ORDER LAYER (DeliveryRequest)
   - Quản lý Đơn hàng Khách (Ai, Hàng gì, Địa chỉ Nhận/Giao, Trạng thái đơn)
   - Độc lập hoàn toàn với thiết bị phần cứng, PLC, Robot và Telemetry Drone
===================================================================================
                                    │
                                    ▼
===================================================================================
2. MISSION ORCHESTRATION LAYER (MissionManager / IntralogisticsMissionRecord)
   - Điều phối Vòng đời Nhiệm vụ tổng quan (order_id, type, status, current_phase)
   - Các pha điều phối: QUEUED → STATION_PROCESSING → DRONE_EN_ROUTE → COMPLETED
   - Bản ghi Database sạch sẽ (KHÔNG lưu các chuỗi mảng JSON FSM step phức tạp)
===================================================================================
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
=======================================   =========================================
3A. STATION OPERATION SERVICE             3B. DRONE FLIGHT SERVICE
   - StationService (Station Controller)     - DroneService (PX4 / MAVLink)
   - Tác vụ: LOAD_PRODUCT, UNLOAD_PRODUCT    - Lệnh bay: GO_TO_WAREHOUSE, GO_TO_CUSTOMER
=======================================   =========================================
                  │                                   │
                  ▼                                   ▼
===================================================================================
4. DEVICE MANAGERS & STATES LAYER
   - PLCManager     : S7-1200 DB15 protocol (Commands DBX0.x, Status DBX2.x)
   - RobotManager   : FAIRINO Robot Arm Socket TCP driver (PICK, STORE, HOME)
   - CameraService  : QR Code Vision scanner & Slot mapping
   - DroneDriver    : MAVLink / PX4 socket connection
===================================================================================
```

---

## 2. Phần cứng & Giao thức Kết nối Mạng LAN

Toàn bộ các thiết bị giao tiếp với Central FastAPI Backend Server thông qua mạng LAN nội bộ:

| Thiết bị | Loại (DeviceType) | IP Mặc định | Giao thức | Chức năng chính |
|----------|-------------------|-------------|-----------|-----------------|
| **UAV01** | `UAV` | `192.168.137.88` | WebSocket / MAVLink | Máy bay không người lái giao/nhận hàng |
| **PLC01** | `PLC` | `192.168.58.10` | Snap7 DB15 Protocol | Điều khiển Kẹp X/Y, Cảm biến Landing Pad, Trục Z |
| **ROBOT01** | `ROBOT` | `192.168.57.2:8090` | TCP/IP Socket (CRLF) | Cánh tay Robot gắp/đặt sản phẩm (Lua Server Port 8090, Slots A1..C3) |
| **CAM01** | `CAMERA` | `192.168.58.50` | RTSP Stream / REST API | Camera quét mã QR sản phẩm nhập kho |

---

## 3. Bảng Ánh xạ PLC DB15 Protocol (Siemens S7-1200 ↔ Backend)
*Chi tiết đầy đủ xem tại [plc-db15-io-mapping.md](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/docs/plc-db15-io-mapping.md)*

### 3.1. Backend → PLC (Lệnh Command Bits & Words)
| Địa chỉ DB15 | Tên Tag (Code) | Kiểu | Ý nghĩa / Chức năng |
|:---:|:---:|:---:|:---|
| **`DB15.DBX0.0`** | `cmd_lock_drone` | BOOL | Yêu cầu PLC đóng cơ cấu kẹp khóa cố định Drone |
| **`DB15.DBX0.1`** | `cmd_unlock_drone` | BOOL | Yêu cầu PLC mở cơ cấu kẹp giải phóng Drone |
| **`DB15.DBX0.2`** | `cmd_target_z` | BOOL | Lệnh kích hoạt chạy trục Z đến tầng DBW8 (Tự tắt khi DBX2.7=1) |
| **`DB15.DBX0.3`** | *Reserved* | BOOL | *Dự phòng* |
| **`DB15.DBX0.4`** | `cmd_stop_plc` | BOOL | Yêu cầu PLC dừng chu kỳ làm việc |
| **`DB15.DBX0.5`** | `cmd_start_plc` | BOOL | Yêu cầu PLC bật hệ thống sẵn sàng hoạt động |
| **`DB15.DBX0.6`** | `cmd_reset_plc` | BOOL | Yêu cầu PLC xóa trạng thái lỗi (Reset Error) |
| **`DB15.DBX0.7`** | `watchdog_heartbeat` | BOOL | Xung nhịp tim Watchdog từ Backend (1s) |
| **`DB15.DBX1.0`** | `cmd_staff_mode_enable` | BOOL | Bật/tắt Chế độ Nhân viên (1 = Staff Mode, 0 = Auto) |
| **`DB15.DBX1.1`** | `cmd_staff_outbound_start`| BOOL | Bắt đầu chu trình Lấy hàng ra Băng tải |
| **`DB15.DBX1.2`** | `cmd_staff_outbound_cancel`| BOOL | Hủy chu trình Lấy hàng ra Băng tải |
| **`DB15.DBX1.3`** | `cmd_staff_inbound_start` | BOOL | Bắt đầu chu trình Thêm hàng từ O1 vào Kho |
| **`DB15.DBX1.4`** | `cmd_staff_inbound_stop` | BOOL | Dừng chu trình Thêm hàng |
| **`DB15.DBW4`** | `staff_target_count` | INT16 | Số lượng kiện hàng yêu cầu xuất/nhập |
| **`DB15.DBW8`** | `target_z_level` | INT16 | Mã tầng Z mục tiêu (0=Home, 1=Hàng A, 2=Hàng B, 3=N1, 4=O1) |

### 3.2. PLC → Backend (Trạng thái Status Bits & Words)
| Địa chỉ DB15 | Tên Tag (Code) | Kiểu | Ý nghĩa / Chức năng |
|:---:|:---:|:---:|:---|
| **`DB15.DBX2.0`** | `drone_detected` | BOOL | Cảm biến phát hiện Drone đã hạ cánh đúng vị trí Pad N1 |
| **`DB15.DBX2.1`** | `plc_locked_state` | BOOL | Trạng thái cơ cấu kẹp khóa Drone đã hoàn thành |
| **`DB15.DBX2.2`** | *Reserved* | BOOL | *Dự phòng (Đã loại bỏ — Thay thế bằng DB15.DBX2.7 & DBW8)* |
| **`DB15.DBX2.3`** | *Reserved* | BOOL | *Dự phòng (Đã loại bỏ — Thay thế bằng DB15.DBX2.7 & DBW8)* |
| **`DB15.DBX2.4`** | `plc_on` | BOOL | PLC đang hoạt động và sẵn sàng nhận lệnh |
| **`DB15.DBX2.5`** | `plc_error` | BOOL | PLC phát hiện lỗi trong quá trình vận hành |
| **`DB15.DBX2.6`** | `emergency_stop` | BOOL | Trạng thái nút dừng khẩn cấp E-Stop được kích hoạt |
| **`DB15.DBX2.7`** | `plc_z_in_position` | BOOL | **Trục Z đã đến tầng mục tiêu và sẵn sàng cho Robot chạy** |
| **`DB15.DBX3.0`** | `sensor_conveyor_head` | BOOL | Cảm biến 1: Đầu băng tải (Vị trí O1 làm việc của Robot) |
| **`DB15.DBX3.1`** | `sensor_conveyor_end` | BOOL | Cảm biến 2: Cuối băng tải (Vị trí Nhân viên) |
| **`DB15.DBX3.2`** | `conveyor_running` | BOOL | Trạng thái Động cơ Băng tải đang chạy |
| **`DB15.DBX3.3`** | `staff_outbound_busy` | BOOL | PLC đang bận chu trình xuất hàng ra băng tải |
| **`DB15.DBX3.4`** | `staff_outbound_done` | BOOL | PLC đã xuất xong toàn bộ số lượng hàng ra băng tải |
| **`DB15.DBX3.5`** | `staff_inbound_busy` | BOOL | PLC đang bận chu trình nạp hàng từ O1 vào kho |
| **`DB15.DBX3.6`** | `staff_inbound_done` | BOOL | PLC đã kết thúc chu trình nạp hàng |
| **`DB15.DBX3.7`** | `staff_mode_active` | BOOL | PLC xác nhận đang ở Chế độ Nhân viên (Staff Mode) |
| **`DB15.DBW6`** | `staff_current_count` | INT16 | Số lượng kiện hàng thực tế đã đếm qua cảm biến |

### 3.3. Liên Động Phần Cứng Robot DO0 & Khóa Trục Z PLC
* **Robot DO0 = 1**: Robot ở vị trí HOME an toàn $\rightarrow$ Cho phép PLC chạy trục Z theo `DBW8`.
* **Robot DO0 = 0**: Robot rời HOME $\rightarrow$ PLC lập tức khóa trục Z chống va chạm cơ khí.
* **PLC DBX2.7 = 1**: Trục Z đến tầng an toàn $\rightarrow$ Backend cho phép Robot bắt đầu vươn tay gắp/cất.

---

## 4. Tác vụ Trạm Docking (Station Operations - Layer 3)

Lớp dịch vụ `StationService` thực thi các tác vụ phần cứng tự động tại Trạm Kho:

### 4.1. Tác vụ `LOAD_PRODUCT` (Xuất Kho Giao Hàng)
1. **PLC Lock**: Gửi `cmd_lock_drone` (`DB15.DBX0.0`) & chờ `plc_locked_state = True` (`DB15.DBX2.1`).
2. **PLC Z to Slot**: Ghi `DB15.DBW8 = 1/2` (tầng ô kho target_slot) & chờ `plc_z_in_position = True` (`DB15.DBX2.7`).
3. **Robot Pick Slot**: FAIRINO Robot gắp hàng từ Ô kho chỉ định (`target_slot`).
4. **QR Verify**: Camera CAM01 kiểm tra đối soát mã QR sản phẩm trước khi nâng Z.
5. **PLC Z to Dock**: Ghi `DB15.DBW8 = 3` (tầng Drone N1) & chờ `plc_z_in_position = True` (`DB15.DBX2.7`).
6. **Robot Place Dock**: FAIRINO Robot đặt hàng lên gá chứa của Drone (`N1`).
7. **PLC Z Home**: Ghi `DB15.DBW8 = 0` (vị trí Home an toàn) & chờ `plc_z_in_position = True` (`DB15.DBX2.7`).
8. **PLC Unlock**: Gửi `cmd_unlock_drone` (`DB15.DBX0.1`) & chờ `plc_locked_state = False` (`DB15.DBX2.1`).
9. **Update Inventory**: Cập nhật Ô kho về trạng thái `EMPTY`.

### 4.2. Tác vụ `UNLOAD_PRODUCT` (Nhập Kho Nhận Hàng)
1. **PLC Lock**: Gửi `cmd_lock_drone` (`DB15.DBX0.0`) & chờ `plc_locked_state = True` (`DB15.DBX2.1`).
2. **PLC Z to Dock**: Ghi `DB15.DBW8 = 3` (tầng Drone N1) & chờ `plc_z_in_position = True` (`DB15.DBX2.7`).
3. **Robot Pick Dock**: FAIRINO Robot gắp hàng từ gá chứa của Drone (`N1`).
4. **PLC Z Home & QR Scan**: Ghi `DB15.DBW8 = 0` đưa Z về vị trí Home & Camera CAM01 quét mã QR sản phẩm.
5. **PLC Z to Slot**: Ghi `DB15.DBW8 = 1/2` (tầng ô kho target_slot) & chờ `plc_z_in_position = True` (`DB15.DBX2.7`).
6. **Robot Store Slot**: FAIRINO Robot cất hàng vào Ô kho trống được cấp phát (`target_slot`).
7. **PLC Z Home**: Ghi `DB15.DBW8 = 0` (vị trí Home an toàn) & chờ `plc_z_in_position = True` (`DB15.DBX2.7`).
8. **PLC Unlock**: Gửi `cmd_unlock_drone` (`DB15.DBX0.1`) & chờ `plc_locked_state = False` (`DB15.DBX2.1`).
9. **Update Inventory**: Cập nhật Ô kho về trạng thái `OCCUPIED` gắn mã `product_id`.

---

## 5. Hướng dẫn Chạy Kiểm thử & Khởi chạy

### 5.1. Khởi chạy Backend Server
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5.2. Khởi chạy Integration Test Kiểm thử Kiến trúc 4 Tầng
```bash
cd backend
python test_decoupled_architecture.py
```

### 5.3. Khởi chạy Frontend Dashboard
```bash
cd frontend
npm run dev -- --host 0.0.0.0
```
Mở trình duyệt truy cập `http://localhost:5173`, chọn tab **🏭 Kho thông minh (Intralogistics)** để vận hành.
