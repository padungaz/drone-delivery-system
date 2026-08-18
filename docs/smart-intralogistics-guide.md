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

### 3.1. PLC → Backend (Trạng thái Status Bits - `DB15.DBX2.x`)
| Tagname | Type | Địa chỉ DB15 | Ý nghĩa |
| :---: | :---: | :---: | :--- |
| `drone_detected` | BOOL | `DB15.DBX2.0` | PLC phát hiện Drone đã hạ cánh đúng vị trí Dock Pad |
| `plc_locked_state` | BOOL | `DB15.DBX2.1` | Trạng thái cơ cấu kẹp khóa Drone đã hoàn thành |
| `plc_z_is_up` | BOOL | `DB15.DBX2.2` | Trạng thái Trục Z đã nâng đến vị trí trên (UP) |
| `plc_z_is_down` | BOOL | `DB15.DBX2.3` | Trạng thái Trục Z đã hạ về vị trí ban đầu (DOWN) |
| `plc_on` | BOOL | `DB15.DBX2.4` | PLC đang hoạt động và sẵn sàng nhận lệnh |
| `plc_error` | BOOL | `DB15.DBX2.5` | PLC phát hiện lỗi trong quá trình vận hành |
| `emergency_stop` | BOOL | `DB15.DBX2.6` | Trạng thái nút dừng khẩn cấp được kích hoạt |

### 3.2. Backend → PLC (Lệnh Command Bits - `DB15.DBX0.x`)
| Tagname | Type | Địa chỉ DB15 | Ý nghĩa |
| :---: | :---: | :---: | :--- |
| `cmd_lock_drone` | BOOL | `DB15.DBX0.0` | Lệnh yêu cầu PLC đóng cơ cấu kẹp khóa cố định Drone |
| `cmd_unlock_drone` | BOOL | `DB15.DBX0.1` | Lệnh yêu cầu PLC mở cơ cấu kẹp giải phóng Drone |
| `cmd_z_up` | BOOL | `DB15.DBX0.2` | Lệnh yêu cầu PLC nâng Trục Z lên vị trí chờ gắp hàng |
| `cmd_z_down` | BOOL | `DB15.DBX0.3` | Lệnh yêu cầu PLC hạ Trục Z về vị trí cất cánh |
| `cmd_stop_plc` | BOOL | `DB15.DBX0.4` | Lệnh yêu cầu PLC dừng chu kỳ làm việc |
| `cmd_start_plc` | BOOL | `DB15.DBX0.5` | Lệnh yêu cầu PLC bật hệ thống sẵn sàng hoạt động |
| `cmd_reset_plc` | BOOL | `DB15.DBX0.6` | Lệnh yêu cầu PLC xóa trạng thái lỗi (Reset Error) |

---

## 4. Tác vụ Trạm Docking (Station Operations - Layer 3)

Lớp dịch vụ `StationService` thực thi các tác vụ phần cứng tự động tại Trạm Kho:

### 4.1. Tác vụ `LOAD_PRODUCT` (Xuất Kho Giao Hàng)
1. **PLC Lock**: Gửi `cmd_lock_drone` (`DB15.DBX0.0`) & chờ `plc_locked_state = True` (`DB15.DBX2.1`).
2. **PLC Z Up**: Gửi `cmd_z_up` (`DB15.DBX0.2`) & chờ `plc_z_is_up = True` (`DB15.DBX2.2`).
3. **Robot Pick Slot**: FAIRINO Robot gắp hàng từ Ô kho chỉ định (`target_slot`).
4. **Robot Place Dock**: FAIRINO Robot đặt hàng lên gá chứa của Drone (`DOCK`).
5. **Robot Home**: FAIRINO Robot quay về vị trí an toàn (`HOME`).
6. **PLC Z Down**: Gửi `cmd_z_down` (`DB15.DBX0.3`) & chờ `plc_z_is_down = True` (`DB15.DBX2.3`).
7. **PLC Unlock**: Gửi `cmd_unlock_drone` (`DB15.DBX0.1`) & chờ `plc_locked_state = False` (`DB15.DBX2.1`).
8. **Update Inventory**: Cập nhật Ô kho về trạng thái `EMPTY`.

### 4.2. Tác vụ `UNLOAD_PRODUCT` (Nhập Kho Nhận Hàng)
1. **PLC Lock**: Gửi `cmd_lock_drone` (`DB15.DBX0.0`) & chờ `plc_locked_state = True` (`DB15.DBX2.1`).
2. **PLC Z Up**: Gửi `cmd_z_up` (`DB15.DBX0.2`) & chờ `plc_z_is_up = True` (`DB15.DBX2.2`).
3. **Robot Pick Dock**: FAIRINO Robot gắp hàng từ gá chứa của Drone (`DOCK`).
4. **Robot Store Slot**: FAIRINO Robot cất hàng vào Ô kho trống được cấp phát (`target_slot`).
5. **Robot Home**: FAIRINO Robot quay về vị trí an toàn (`HOME`).
6. **PLC Z Down**: Gửi `cmd_z_down` (`DB15.DBX0.3`) & chờ `plc_z_is_down = True` (`DB15.DBX2.3`).
7. **PLC Unlock**: Gửi `cmd_unlock_drone` (`DB15.DBX0.1`) & chờ `plc_locked_state = False` (`DB15.DBX2.1`).
8. **Update Inventory**: Cập nhật Ô kho về trạng thái `OCCUPIED` gắn mã `product_id`.

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
