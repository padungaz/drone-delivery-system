# Hệ Thống Kho Thông Minh & Trạm Giao Nhận Drone (Smart Intralogistics & UAV Fleet System)
## Báo Cáo Tiến Độ Dự Án & Kế Hoạch Triển Khai (task.md)

Cập nhật lần cuối: **18/08/2026**

---

## 🎯 1. Tổng Quan Hệ Thống
Hệ thống tự động hóa kho thông minh kết hợp giao nhận bằng máy bay không người lái (UAV) gồm 4 tầng kiến trúc tách biệt (**4-Layer Decoupled Architecture**):
1. **Khách hàng & Đơn hàng (Customer Order Layer)**: Quản lý yêu cầu xuất/nhập kho (`DeliveryRequestRecord`), trạng thái đơn hàng (`PENDING`, `PROCESSING`, `DELIVERED`, `FAILED`).
2. **Điều phối Nhiệm vụ (Mission Orchestrator - Layer 2)**: Quản lý vòng đời nhiệm vụ (`IntralogisticsMissionRecord`), điều phối hàng đợi FIFO (`MissionQueueManager`), tự động gán UAV và đồng bộ hóa tiến trình trạm.
3. **Trạm Docking & Dịch Vụ Phần Cứng (Station Task Service - Layer 3)**: Chuỗi FSM 11 bước tự động điều khiển Cánh tay Robot FAIRINO FR3 (LUA TCP Socket Port 8090), PLC Siemens S7-1200 (Profinet DB15 Snap7), Camera Vision quét mã QR (CAM01), Bãi đáp Drone Pad N1.
4. **Hệ Thống Đội Bay UAV (UAV Fleet System - Layer 4)**: Quản lý trạng thái đội bay (`UAV01`, `UAV02`, `UAV03`...) liên lạc qua tín hiệu Event-Driven độc lập với trạm kho (`signal_drone_arrived`, `signal_drone_depart_home`, `signal_drone_depart_delivery`).

---

## ✅ 2. Những Gì ĐÃ LÀM ĐƯỢC (Work Accomplished - Cập nhật 18/08/2026)

### 🛡️ 2.1. Cơ Chế Khóa An Toàn Độc Lập (Safety Interlock Manager)
- [x] **Singleton Service `DeviceLockManager` ([device_lock_manager.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/device_lock_manager.py))**:
  - Tự động khóa trạm và thiết bị (`PLC01`, `ROBOT01`) khi có Auto Mission đang thực thi chu trình phần cứng (`STATION_PROCESSING`).
  - Toàn bộ các API manual điều khiển chuyển động (`POST /api/plc/lock`, `POST /api/plc/hatch`, `POST /api/robot/pick`, `POST /api/robot/store`, `POST /api/device/send-raw-command`...) tự động chặn và trả về **`HTTP 409 Conflict`** kèm mã Mission đang giữ khóa.
  - **Ngoại lệ An toàn**: Các lệnh Dừng Khẩn Cấp (`STOP_PLC`, `EMERGENCY_STOP`, `RESET_PLC`) luôn được phép can thiệp tức thì.
  - Cung cấp API `GET /api/device/lock-status` để HMI giám sát trạng thái khóa trạm theo thời gian thực.

---

### ⚡ 2.2. Chuẩn Hóa Chế Độ Hệ Thống & Nút Khởi Động Kho Trạm (AUTO Start Routine)
- [x] **FSM Trạng Thái Vận Hành ([system_mode_manager.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/system_mode_manager.py))**:
  - Phân tách rõ ràng giữa **Chọn chế độ (Mode Selection)** và **Phát lệnh vận hành (System Start)**.
  - Quản lý 4 trạng thái con của AUTO: `STANDBY` (Đèn vàng chờ Start) $\rightarrow$ `RUNNING` (Đèn xanh chạy tự động) $\rightarrow$ `PAUSED` (Tạm dừng) $\rightarrow$ `ERROR`.
  - Khi chuyển sang `MANUAL`: Toàn bộ Dispatcher tự động ngắt, đơn hàng mới vào hàng chờ `WAITING`.
  - Khi chuyển sang `AUTO`: Mặc định vào trạng thái `STANDBY` an toàn (chưa tự ý kích hoạt chuyển động cơ khí).
- [x] **Quy Trình Tiền Khởi Động 5 Bước (Pre-flight Diagnostic & Homing Routine)**:
  - Endpoint `POST /api/system/start-auto` ([fleet.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/api/fleet.py)):
    1. Kiểm tra an toàn E-Stop & Safety Interlock.
    2. PLC S7-1200: Gửi lệnh `START_PLC`, reset lỗi DB15, đưa thang nâng Z về vị trí an toàn `Z_DOWN`.
    3. FAIRINO Robot: Gửi lệnh `MOVE_HOME` đưa tay máy về tư thế chuẩn an toàn.
    4. Chuyển trạng thái `auto_state = "RUNNING"`, kích hoạt Scheduler.
    5. Quét và tự động nạp đơn hàng đầu tiên từ hàng đợi FIFO.
  - Endpoint `POST /api/system/pause-auto`: Tạm dừng hệ thống tự động an toàn mà không cần thoát chế độ AUTO.
  - Endpoint `POST /api/system/resume-queue`: Cho phép Operator tiếp tục xử lý hàng đợi sau khi kiểm tra thiết bị.
- [x] **Giao Diện HMI Header Thông Minh ([SystemHeader.tsx](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/frontend/src/components/layout/SystemHeader.tsx), [styles.css](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/frontend/src/styles.css))**:
  - `MANUAL`: Nút hiển thị `🔒 KHÓA TỰ ĐỘNG` (disabled).
  - `AUTO (STANDBY)`: Nút **`▶ START KHO TRẠM`** màu xanh lục Neon với hiệu ứng nhịp đập (**Pulse Glow Animation**) thu hút Operator bấm.
  - `AUTO (RUNNING)`: Badge **`🟢 AUTO RUNNING`** (đèn xanh nhấp nháy) kèm nút **`⏸️ TẠM DỪNG`**.
  - `AUTO (PAUSED)`: Nút **`▶ TIẾP TỤC CHẠY`** màu hổ phách.

---

### 📦 2.3. Sửa Triệt Để Lỗi Hàng Đợi FIFO & Cơ Chế Fail-Safe Khi Sự Cố
- [x] **Sửa Deadlock Hàng Đợi ([mission_manager.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/mission_manager.py))**:
  - Sửa phương thức `get_active_mission()`: Chỉ xét nhiệm vụ có trạng thái `RUNNING` là active. Loại bỏ hoàn toàn lỗi nhiệm vụ `WAITING` bị đếm nhầm khiến hàng chờ bị nghẽn (deadlock).
- [x] **Cơ Chế Fail-Safe Ngắt Chuỗi Lỗi Dây Chuyền**:
  - Khi nhiệm vụ gặp lỗi phần cứng (`_abort_mission`), hệ thống đánh dấu `FAILED`, giải phóng khóa interlock, phát cảnh báo `SYSTEM_ALERT` qua WebSocket và **dừng hàng đợi tự động** (không tự ý đẩy tiếp đơn tiếp theo vào vòng lặp lỗi).

---

### 🤖 2.4. Chuẩn Hóa Giao Thức Robot FAIRINO LUA & PLC DB15
- [x] **Chuẩn Hóa Vị Trí Dock N1 ([robot_manager.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/robot_manager.py), `code-robot.lua`)**:
  - Tự động map toàn bộ các alias `"DOCK"`, `"PAD"`, `"PAD_N1"` thành vị trí `"N1"` chuẩn theo script Lua của Robot FR3 (Port 8090).
  - `PICK_UAV` $\rightarrow$ payload `"PICK N1"`, `PLACE_UAV` $\rightarrow$ payload `"STORE N1"`.
  - Khắc phục lỗi Socket: Khi mất kết nối hoặc nhận phản hồi `FAILED`/`BUSY`, set `state = "ERROR"` và raise Exception để FSM rollback an toàn thay vì nuốt lỗi.
- [x] **Chuẩn Hóa PLC DB15 & Cảm Biến Landing ([plc_manager.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/plc_manager.py))**:
  - Lệnh `UNLOCK_DRONE` không làm mất trạng thái `drone_detected = True`. Cảm biến chỉ chuyển về `False` khi UAV thực sự cất cánh rời trạm (`signal_drone_depart_home` / `signal_drone_depart_delivery` trong `fleet_manager.py`).
- [x] **Chuẩn Hóa Station Service FSM ([station_service.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/station_service.py))**:
  - Đổi toàn bộ vị trí gắp/đặt từ `"DOCK"` sang `"N1"` ở cả 2 chu trình: `execute_load_product` (Xuất kho) và `execute_unload_product` (Nhập kho).

---

### 🔄 2.5. Hệ Thống Tự Động Thu Hồi Sau Khởi Động (Startup Recovery Manager)
- [x] **Dịch Vụ `RecoveryManager` ([recovery_manager.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/recovery_manager.py), [main.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/main.py))**:
  - Tích hợp vào `lifespan` khi Backend khởi động lại.
  - Tự động quét và thu hồi các nhiệm vụ mồ côi bị dở dang (`RUNNING` / `STATION_PROCESSING`) chuyển thành `FAILED` với lý do `SYSTEM_RESTART_ORPHANED_TASK`.
  - Reset toàn bộ khóa interlock trong RAM và kiểm tra trạng thái an toàn cơ khí (kẹp PLC, tay gắp Robot).

---

### 🧪 2.6. Bộ Test Tự Động (Automated Test Suites - 100% Passed)
- [x] **`test_camera_modes.py` (3/3 PASSED)**:
  - Test 1: Đổi cấu hình CAM01 chuyển đổi tức thì giữa Real USB Camera và Simulator Mode.
  - Test 2: Chu trình StationService FSM 11 bước tự động gọi CameraManager.scan_qr_auto ở Bước 5 (QR Verify) và Bước 8 (QR Scan).
  - Test 3: Các API điều khiển thủ công Camera (Start/Stop stream, Quét thử QR, Cấu hình) hoạt động chính xác.
- [x] **`test_interlock_and_failsafe.py` (5/5 PASSED)**:
  - Test 1: Safety Interlock chặn lệnh manual điều khiển PLC/Robot khi Auto Mission đang chạy (HTTP 409). Cho phép lệnh STOP khẩn cấp (HTTP 200).
  - Test 2: Chế độ MANUAL ngăn chặn Auto Dispatcher và giữ đơn mới ở hàng chờ WAITING.
  - Test 3: Fairino Robot tự động chuyển đổi vị trí Dock thành `N1` chuẩn giao thức Lua.
  - Test 4: Lệnh PLC UNLOCK bảo toàn tín hiệu Drone Landing (`drone_detected = True`) cho tới khi cất cánh.
  - Test 5: Recovery Manager tự động phát hiện và thu hồi nhiệm vụ mồ côi khi khởi động server.
- [x] **`test_auto_start_feature.py` (4/4 PASSED)**:
  - Test 1: Chuyển sang AUTO mặc định ở trạng thái STANDBY an toàn.
  - Test 2: Nút `start-auto` kích hoạt quy trình Homing thiết bị (PLC Z-Down, Robot Home), chuyển sang `RUNNING` và tự động dispatch đơn hàng FIFO.
  - Test 3: Nút `pause-auto` tạm dừng Scheduler và `resume-queue` kích hoạt lại.
  - Test 4: Chuyển sang MANUAL vô hiệu hóa hoàn toàn Auto Scheduler.
- [x] **`test_smart_intralogistics.py` & `test_decoupled_architecture.py` (PASSED)**:
  - Toàn bộ chu trình Nhập kho (`DRONE_PICKUP`) và Xuất kho (`DRONE_DELIVERY`) 11 bước và kiến trúc 4 tầng hoạt động trơn tru.

---

### 📷 2.7. Tích Hợp Camera USB Thật & Tách Biệt Chế Độ Auto/Manual
- [x] **Tích hợp Camera USB Thật ([qr_scanner_service.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/qr_scanner_service.py), [camera_manager.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/camera_manager.py))**:
  - Đọc trực tiếp frame từ Camera USB cắm trên máy tính Backend (DirectShow trên Windows / VideoCapture).
  - Tự động nhận diện và giải mã mã QR qua `cv2.QRCodeDetector`.
  - Hỗ trợ Live Stream MJPEG video feed (`GET /api/inventory/camera-scan/video-feed`) đưa trực tiếp lên giao diện Dashboard HMI.
- [x] **Chế Độ AUTO Trong FSM Trạm ([station_service.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/station_service.py))**:
  - Bước 5 (Xuất kho - `QR_VERIFY`): Gọi `CameraManager.scan_qr_auto()` xác thực mã QR của kiện hàng.
  - Bước 8 (Nhập kho - `QR_SCAN`): Gọi `CameraManager.scan_qr_auto()` quét mã QR kiện hàng để lấy mã sản phẩm thật lưu vào ô kho.
  - Loại bỏ hoàn toàn các lệnh `asyncio.sleep(0.5)` giả lập.
- [x] **Chế Độ MANUAL ([CameraVision.tsx](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/frontend/src/components/vision/CameraVision.tsx))**:
  - Bật/Tắt Live stream video trực tiếp từ USB Camera.
  - Quét thử nghiệm mã QR thủ công, nhập mã QR thủ công (Manual Override).
  - Chuyển đổi linh hoạt giữa `🔌 Real USB Camera` và `🤖 Simulator Mode`.
- [x] **Loại Bỏ Silent Fallback ([plc_manager.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/plc_manager.py))**:
  - Khi PLC ở chế độ Real Hardware mà mất kết nối, hệ thống raise `ConnectionError` rõ ràng thay vì âm thầm rơi về mô phỏng.

### 🔄 2.8. Tinh Gọn FSM Phần Cứng, Bỏ Robot Home Thừa & Tự Động Tắt Camera (Cập nhật 20/08/2026)
- [x] **Khởi Động `▶ START KHO TRẠM` ([fleet.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/api/fleet.py))**:
  - Bỏ lệnh `MOVE_HOME` từ Backend, giao quyền liên động cơ khí an toàn giữa Trục Z và Robot cho PLC S7-1200 xử lý trực tiếp qua hardware I/O.
- [x] **Tinh Gọn Chu Trình Nhập Kho (`DRONE_PICKUP` / `UNLOAD_PRODUCT`) ([station_service.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/station_service.py))**:
  - Loại bỏ các bước gọi `MOVE_HOME` trung gian qua Socket.
  - Chuỗi mới: `DRONE_DETECT` $\rightarrow$ `LOCK_DRONE` $\rightarrow$ `PLC_Z_UP` $\rightarrow$ `ROBOT_PICK_DOCK` $\rightarrow$ `PLC_Z_DOWN` $\rightarrow$ `QR_SCAN` $\rightarrow$ `ROBOT_STORE_SLOT` $\rightarrow$ `UNLOCK_DRONE` $\rightarrow$ `TAKEOFF_COMPLETE`.
- [x] **Tối Ưu Chu Trình Xuất Kho (`DRONE_DELIVERY` / `LOAD_PRODUCT`) ([station_service.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/station_service.py))**:
  - Chuỗi mới: `DRONE_DETECT` $\rightarrow$ `LOCK_DRONE` $\rightarrow$ `ROBOT_PICK_SLOT` $\rightarrow$ **`QR_VERIFY`** $\rightarrow$ **`PLC_Z_UP`** $\rightarrow$ `ROBOT_PLACE_DOCK` $\rightarrow$ `PLC_Z_DOWN` $\rightarrow$ `UNLOCK_DRONE` $\rightarrow$ `TAKEOFF_COMPLETE`.
  - Đối soát mã QR ngay tại vị trí dưới trước khi nâng trục Z, chống lãng phí chu kỳ cơ khí khi sai hàng.
- [x] **Quản Lý Vòng Đời Camera On-Demand & Báo Lỗi Từng Giai Đoạn**:
  - Bọc `try ... finally` đảm bảo luôn gọi `CameraManager.stop_camera()` sau khi quét xong hoặc khi có Exception.
  - Bổ sung mã lỗi chi tiết tiếng Việt (`ERROR_DRONE_NOT_DETECTED`, `ERROR_PLC_LOCK_FAILED`, `ERROR_ROBOT_PICK_FAILED`, `ERROR_QR_SCAN_FAILED`, `ERROR_QR_VERIFY_FAILED`, `ERROR_PLC_Z_UP_FAILED`, `ERROR_PLC_Z_DOWN_FAILED`, `ERROR_PLC_UNLOCK_FAILED`).

---

## ⏳ 3. Những Gì CHƯA LÀM ĐƯỢC / CẦN NÂNG CẤP (Pending & Improvements)
- [ ] **Kiểm thử trực tiếp trên phần cứng vật lý tại xưởng**:
  - Cần cắm cáp LAN kết nối thực tế với Controller Robot FAIRINO FR3 (IP `192.168.58.2:8090`) và PLC Siemens S7-1200 (IP `192.168.58.10`, Rack 0, Slot 1) để xác thực thời gian đáp ứng cơ khí thật.
- [ ] **Báo cáo thống kê hiệu suất ca làm việc (OEE Analytics)**:
  - Lưu trữ thời gian chu kỳ (Cycle Time) từng bước vào database để vẽ biểu đồ thống kê số lượng đơn xử lý theo giờ/ngày.
- [ ] **Âm thanh cảnh báo (Audio Alerts)**:
  - Tích hợp âm thanh tiếng bíp / còi còi khi Robot hoàn thành đơn, khi trạm Start Auto, hoặc khi phát hiện Dừng Khẩn Cấp (E-Stop).

---

## 🚀 4. KẾ HOẠCH TIẾP THEO (Next Steps Roadmap)

1. **Giai đoạn 1: Chạy thử nghiệm chuỗi đơn hàng liên hoàn (End-to-End Stress Test)**:
   - Tạo kịch bản 5 đơn hàng liên tiếp (3 Nhận hàng, 2 Giao hàng).
   - Kiểm tra việc luân chuyển tự động giữa Camera USB $\leftrightarrow$ Robot FR3 $\leftrightarrow$ PLC S7-1200 trên Dashboard HMI.
2. **Giai đoạn 2: Tối ưu hóa trải nghiệm tương tác (UX Polish)**:
   - Thêm hiệu ứng âm thanh cảnh báo công nghiệp (Audio sound effects cho sự kiện Start/Done/Error).
   - Bổ sung phím tắt nhanh trên bàn phím (Keyboard Shortcuts: `Space` = Pause/Resume, `Esc` = E-Stop).
3. **Giai đoạn 3: Đóng gói và hướng dẫn bàn giao**:
   - Viết tài liệu hướng dẫn vận hành cho kỹ sư trực ca HMI.
   - Tạo script khởi động 1-click cho toàn bộ hệ sinh thái (Backend Uvicorn + Frontend Vite + Hardware Drivers).


