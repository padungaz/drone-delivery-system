# BÁO CÁO CÔNG VIỆC & TASK LIST

## 📅 Nngày: 30/07/2026

---

## 🟢 1. Các công việc đã hoàn thành hôm nay (Work Completed)

### 1.1. Phân tích Kiến trúc & Logic Mã nguồn Companion (Pi 5)
- [x] Phân tích luồng **Điều khiển Thủ công** (`SET_MODE`, `ARM`/`DISARM`, `MOVE_RELATIVE`, `STEP_COMMAND`).
- [x] Phân tích luồng **Bay Tự động Nhiệm vụ (MISSION Flight)** qua State Machine (FSM).

### 1.2. Giải quyết Lỗi Cất cánh (Mode Collision) & Refactor Companion
- [x] Thống nhất áp dụng **Phương pháp A (Dùng Mode TAKEOFF chuẩn PX4)**.
- [x] **Refactor `companion/src/mission_manager/manager.py` (12 sửa đổi):**
  - Tách biệt hoàn toàn `TAKEOFF` (do PX4 tự cất cánh) và `OFFBOARD` (chỉ bật khi bay GPS navigation).
  - Sửa lỗi `STEP TAKEOFF` không còn kích hoạt Offboard keepalive khi ở dưới mặt đất.
  - Sửa các lỗi runtime: `self.aruco_landing` → `self.vision`, `send_status_event` → `send_error`, sửa tên biến config (`TAKEOFF_ALTITUDE_M`, `DESCEND_ALTITUDE_M`).
  - Sửa các lỗi bất đồng bộ thread-safe (`asyncio.create_task` → `asyncio.run_coroutine_threadsafe`).
- [x] **Refactor `companion/src/mavlink_service/controller.py` (2 sửa đổi):**
  - `_send_offboard_position_hold()` chỉ phát setpoint velocity 0 m/s hold vị trí.
  - Luồng Offboard keepalive tự động tắt khi PX4 ra khỏi mode Offboard.
- [x] **Commit & Git Push:** Đã push toàn bộ thay đổi lên branch `main` GitHub repository `padungaz/drone-delivery-system`.

### 1.3. Chẩn đoán Log Thực tế từ Raspberry Pi 5
- [x] Giải thích lý do drone không tăng ga cất cánh (`GPS Sat = 0`, thiếu GPS Lock).
- [x] Giải thích lý do spam log `Forcing LAND mode for final touchdown` (drone ở mặt đất `AltAGL = 0.09m < 0.4m`, luồng ArUco 25Hz liên tục ép mode `LAND`).
- [x] Giải thích nguyên nhân `Invalid transition: PRECISION_LANDING -> IDLE` khi chạy Step-by-Step thủ công.

---

## 🟡 2. Các công việc cần làm vào buổi tiếp theo (Next Tasks)

### 2.1. Cập nhật FSM Transitions (`companion/src/state_machine/states.py`)
- [ ] Bổ sung `DroneState.IDLE` vào bảng `TRANSITIONS[DroneState.PRECISION_LANDING]` để khi chạy Step-by-Step thủ công, hạ cánh xong FSM chuyển về `IDLE` êm ái mà không bắn warning log.

### 2.2. Tối ưu Luồng `_run_landing_target_publisher` (Hạ cánh ArUco)
- [ ] Thêm kiểm tra điều kiện `self.mavlink.telemetry.armed == True` trước khi gọi `self.mavlink.land()` ở luồng 25Hz, tránh việc spam log `Forcing LAND mode for final touchdown` khi drone đã disarm hoặc chưa cất cánh.

### 2.3. Thử nghiệm Thực địa / Thử nghiệm Bay (Flight Test)
- [ ] Kiểm tra tín hiệu GPS (đảm bảo `GPS Sat >= 6` hoặc có EKF2 position estimate) trước khi phát lệnh `TAKEOFF`.
- [ ] Chạy thử nghiệm Manual Step-by-Step: `ARM` → `TAKEOFF` → `NAV_GPS` → `SEARCH_ARUCO` → `PRECISION_LANDING`.
- [ ] Chạy thử nghiệm Full Auto Mission (`START_MISSION`).
