# Hệ Thống Kho Thông Minh & Trạm Giao Nhận Drone (Smart Intralogistics & UAV Fleet System)
## Báo Cáo Tiến Độ Dự Án & Kế Hoạch Triển Khai (task.md)

Cập nhật lần cuối: **17/08/2026**

---

## 🎯 1. Tổng Quan Hệ Thống
Hệ thống tự động hóa kho thông minh kết hợp giao nhận bằng máy bay không người lái (UAV) gồm 4 tầng kiến trúc:
1. **Khách hàng & Đơn hàng**: Quản lý đơn hàng xuất/nhập kho (Inbound / Outbound).
2. **Điều phối Nhiệm vụ (Mission Orchestrator - Layer 2)**: Quản lý hàng chờ FIFO, tự động gán UAV và kích hoạt quy trình trạm Docking.
3. **Trạm Docking & Phần Cứng**: Điều khiển tự động/thủ công Cánh tay Robot FAIRINO FR3 (LUA TCP Socket Port 8090), PLC Siemens S7-1200 (Profinet/Snap7), Camera Vision quét mã QR (CAM01), Bãi đáp Drone Pad N1.
4. **Hệ Thống Đội Bay UAV (UAV Fleet System)**: Quản lý trạng thái đội bay (UAV01, UAV02, UAV03...) liên lạc qua tín hiệu Event-Driven độc lập với trạm kho.

---

## ✅ 2. Những Gì ĐÃ LÀM ĐƯỢC (Work Accomplished)

### 🎛️ 2.1. Quản Lý Chế Độ Toàn Cục Hệ Thống (`🤖 AUTO` $\leftrightarrow$ `🎮 MANUAL`)
- [x] **Backend Singleton `SystemModeManager`**: Quản lý chế độ toàn cục (`AUTO` | `MANUAL`), cung cấp `GET /api/system/mode` và `POST /api/system/mode`, phát realtime qua WebSocket `/ws/system`.
- [x] **Khóa An Toàn FSM (Handshake Safety Lock)**: Khi ở `MANUAL`, tự động chặn `auto_dispatch_next_mission()` để kỹ sư can thiệp độc lập từng thiết bị mà không bị xung đột với quy trình tự động.
- [x] **Công Tắc Chuyển Đổi Trên Header**: Bổ sung nút bấm Cyber Emerald/Amber Glow Pulse trên `SystemHeader.tsx` đồng bộ tức thì trên toàn giao diện.

### 🛡️ 2.2. Giao Diện & Thao Tác Thủ Công An Toàn Theo Chế Độ
- [x] **PLC Siemens S7-1200 (`PLCMonitor.tsx`)**:
  - `AUTO`: Ẩn hoàn toàn bảng điều khiển thủ công, hiển thị card giám sát chuẩn công nghiệp.
  - `MANUAL`: Mở khóa toolbar thủ công (Khóa/Mở ngàm Drone, Nâng/Hạ trục Z, Start/Stop/Reset nguồn PLC, Cảm biến Drone đáp/Bãi trống).
- [x] **Camera Vision QR Scanner (`CameraVision.tsx`)**:
  - `AUTO`: Ẩn thanh công cụ quét thủ công.
  - `MANUAL`: Mở khóa nút bật/tắt RTSP Stream, ô nhập mã QR test và nút kích hoạt quét barcode.
- [x] **Cánh Tay Robot FAIRINO FR3 (`QuickControlPanel.tsx`)**:
  - Tái cấu trúc chuẩn giao diện công nghiệp đồng bộ 100% với PLC (Khối phần cứng Controller Fairino FR3, dàn LED `SERVO`, `BRAKE`, `AUTO/MANUAL`, chân IO Terminal, bảng thông số kết nối TCP Socket `192.168.58.2:8090`, và **4 Indicator Boxes**: `Mode`, `Gripper`, `Target Pos`, `Servo Safety`).
  - **Giữ nguyên trạng thái ở cả 2 chế độ**: Khi chuyển sang `MANUAL`, không bị ẩn bảng thông số mà hiển thị thanh điều khiển thủ công gọn gàng docked ngay bên dưới.
  - Bổ sung trọn bộ lệnh Robot: `🏠 Vị trí HOME`, `⏸️ Vị trí STANDBY`, `📷 Vị trí Soi QR`, `📤 Gắp Ô [A1..C3]`, `📥 Thả Ô [A1..C3]`, `🛬 Gắp Từ UAV`, `🚀 Thả Lên UAV`, `🔓 Mở Kẹp`, `🔒 Đóng Kẹp`.
- [x] **Tối Ưu Bố Cục**: Loại bỏ hoàn toàn bảng `🕹️ JOG CONTROLLER` để tạo bố cục hàng giữa 3 cột cân đối, thoáng mắt và chuẩn công nghiệp.

### 📋 2.3. Tái Cấu Trúc Hoàn Toàn Thẻ `CURRENT TASK MONITOR`
- [x] **Thông Tin Đơn Hàng Đang Thực Thi**: Hiển thị rõ ràng Mã Đơn (`#ORD-XXXX / #MISSION-XX`), Tên sản phẩm (`PRD-XXXX`), Ô kho đích (`Ô [A2]`), Phương tiện (`UAV-01`), Trạng thái (`RUNNING`).
- [x] **Phân Định Loại Nhiệm Vụ Rõ Ràng**:
  - Badge dạ quang: **`📥 NHẬN HÀNG (INBOUND)`** (Emerald Green) vs **`📤 GIAO HÀNG (OUTBOUND)`** (Amber / Rose).
- [x] **Danh Sách 6 Bước Trực Quan Động Theo Nghiệp Vụ**:
  - **Khi Nhận hàng (Inbound)**: `UAV tiếp cận & đáp Pad N1` $\rightarrow$ `PLC khóa ngàm & hạ trục Z` $\rightarrow$ `Robot gắp kiện hàng từ UAV` $\rightarrow$ `Robot đưa hàng soi mã QR CAM01` $\rightarrow$ `Robot cất hàng vào Ô Kho [Slot]` $\rightarrow$ `Robot về Home / Hoàn tất`.
  - **Khi Giao hàng (Outbound)**: `Robot gắp hàng từ Ô Kho [Slot]` $\rightarrow$ `Robot quét mã QR kiểm tra hàng` $\rightarrow$ `Robot đặt kiện hàng lên lưng UAV N1` $\rightarrow$ `PLC nâng trục Z & mở ngàm sẵn sàng` $\rightarrow$ `UAV cất cánh rời trạm đi giao` $\rightarrow$ `Robot & Trạm về trạng thái Chờ (Ready)`.
  - Hiển thị icon trạng thái từng bước: `✓` Hoàn thành, `🔵` Đang xử lý (nhấp nháy neon), `○` Chờ.
- [x] **Danh Sách Đơn Hàng Tiếp Theo (FIFO Queue)**:
  - Tự động lấy danh sách hàng đợi thời gian thực, hiển thị thứ tự `#1, #2, #3`, mã đơn, loại đơn, ô kho đích, UAV và trạng thái `Chờ lượt`.

### 🚁 2.4. Đội Bay UAV (UAV Fleet System) & Mô Phỏng Chuỗi Đơn
- [x] Quản lý đội bay nhiều Drone (`UAV01`, `UAV02`, `UAV03`...) với các trạng thái (`READY`, `FLYING_TO_WAREHOUSE`, `LANDED`, `LOADING`, `FLYING_DELIVERY`, `RETURN_HOME`, `OFFLINE`).
- [x] Bộ nút mô phỏng điều khiển UAV linh hoạt: *Mô phỏng UAV 1 đáp bãi N1, UAV 1 về Home, UAV 2 đáp bãi, UAV 2 rời bãi đi giao hàng*.

---

## ⏳ 3. Những Gì CHƯA LÀM ĐƯỢC / CẦN NÂNG CẤP (Pending & Improvements)
- [ ] **Kiểm thử trực tiếp trên phần cứng vật lý tại xưởng**:
  - Cần cắm cáp LAN kết nối thực tế với Controller Robot FAIRINO FR3 (IP `192.168.58.2:8090`) và PLC Siemens S7-1200 (IP `192.168.58.10`, Rack 0, Slot 1) để xác thực thời gian đáp ứng cơ khí thật (thay cho Simulator Mode).
- [ ] **Báo cáo thống kê hiệu suất ca làm việc (OEE Analytics)**:
  - Lưu trữ thời gian chu kỳ (Cycle Time) từng bước vào database để vẽ biểu đồ thống kê số lượng đơn xử lý theo giờ/ngày.
- [ ] **Âm thanh cảnh báo (Audio Alerts)**:
  - Chưa tích hợp âm thanh tiếng bíp khi Robot hoàn thành đơn hoặc khi PLC kích hoạt dừng khẩn cấp (E-Stop).

---

## 🚀 4. KẾ HOẠCH TIẾP THEO (Next Steps Roadmap)

1. **Giai đoạn 1: Chạy thử nghiệm chuỗi đơn hàng liên hoàn (End-to-End Stress Test)**:
   - Tạo kịch bản 5 đơn hàng liên tiếp (3 Nhận hàng, 2 Giao hàng).
   - Kiểm tra việc luân chuyển tự động giữa UAV01 $\leftrightarrow$ UAV02 $\leftrightarrow$ Robot FR3 $\leftrightarrow$ PLC S7-1200 trên Dashboard HMI.
2. **Giai đoạn 2: Tối ưu hóa trải nghiệm tương tác (UX Polish)**:
   - Thêm hiệu ứng âm thanh cảnh báo công nghiệp (Audio sound effects cho sự kiện Start/Done/Error).
   - Bổ sung phím tắt nhanh trên bàn phím (Keyboard Shortcuts: `Space` = Pause/Resume, `Esc` = E-Stop).
3. **Giai đoạn 3: Đóng gói và hướng dẫn bàn giao**:
   - Viết tài liệu hướng dẫn vận hành cho kỹ sư trực ca HMI.
   - Tạo script khởi động 1-click cho toàn bộ hệ sinh thái (Backend Uvicorn + Frontend Vite + Hardware Drivers).
