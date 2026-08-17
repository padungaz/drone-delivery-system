# Kế Hoạch Tích Hợp Dữ Liệu Thực & Backend WebSockets Vào Giao Diện HMI

Ngày khởi tạo: **16/08/2026**

---

## 🎯 Mục Tiêu Tổng Quan
Đấu nối trực tiếp giao diện HMI công nghiệp mới (`HmiDashboard.tsx`) với hệ thống WebSockets (`/ws/system` và `/ws/drone`) cùng tập hợp REST APIs backend để vận hành thực tế trạm Kho thông minh, Robot FAIRINO FR3, PLC Siemens S7-1200 và Máy bay Drone UAV.

---

## 📋 Danh Sách Hạng Mục Công Việc (Task List)

### Phase 1: Tích Hợp WebSockets & Real-time Hardware Data
- [x] **Tích hợp `useIntralogisticsWS()` & `useWebSocket()` vào `HmiDashboard`**:
  - Đấu nối trạng thái kết nối `sysWsConnected`, `uavOnline`, `plcOnline`, `robotOnline`, `cameraOnline` vào `SystemHeader`.
  - Đồng bộ dữ liệu cờ `DB15` thật từ `plc` (`drone_detected`, `plc_locked_state`, `plc_z_is_up`, `emergency_stop`) vào `PLCMonitor`.
  - Đồng bộ góc xoay 6 khớp real-time `robot.joint_positions` và vị trí TCP `robot.cartesian_position` vào `RobotStatusCard`, `JointControlPanel` và `RobotDigitalTwin`.
  - Đồng bộ danh sách ô kho `storage` thật từ backend SQLite database vào `WarehouseGrid`.
  - Đồng bộ nhiệm vụ `activeMission` và `stationOp` thật từ Orchestrator FSM vào `TaskMonitor`.

---

### Phase 2: Đấu Nối Lệnh Điều Khiển Real-time APIs
- [x] **Gửi Lệnh Robot & PLC Thực**:
  - Nút bấm `HOME`, `PICK`, `STORE`, `PLACE_PAD`, `OPEN/CLOSE GRIPPER` -> Gọi `sendRobotCommand(cmd, slot)`.
  - Nút `E-STOP` -> Gọi `sendPlcCommand('stop')` dừng khẩn cấp PLC và báo động hệ thống.
  - Tích hợp kiểm thử kết nối thiết bị thời gian thực trong Modal Cấu hình Phần cứng.

---

### Phase 3: Đa View Tab Navigation & Split Operations Mode
- [x] **Chuyển Đổi Linh Hoạt Giữa HMI & Chế Độ Bay GCS**:
  - Tab 🏭 **HMI Kho Thông Minh** (FAIRINO Cobot Cell Dashboard)
  - Tab 🗺️ **Bản Đồ Live Map GPS Drone** (`MapPanel` + `TelemetryPanel`)
  - Tab 📋 **Quản Lý Đơn Hàng Khách** (`DeliveryRequestsPanel`)
  - Tab 🧩 **Chế Độ Song Song (Split Operations View)**

---

### Phase 4: Kiểm Thử & Xác Minh Toàn Hệ Thống
- [x] Chạy `npx tsc --noEmit` đảm bảo 0 lỗi TypeScript.
- [x] Thử nghiệm phát lệnh thực tế giữa Frontend HMI và Backend FastAPI Server.
