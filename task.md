# 📋 KHỦNG KẾ HOẠCH NÂNG CẤP ADMIN FRONTEND (SMART INTRALOGISTICS & DRONE GCS)

## 🎯 Mục tiêu
Nâng cấp toàn bộ Giao diện Quản trị (Admin Frontend) theo phong cách **Cyber-Industrial High-Tech Command Center**, kết hợp cảm hứng từ **NASA Mission Control**, **Siemens Industrial IoT**, **Smart Factory Digital Twin** và **Drone Ground Control Station (GCS)**.

## ⚠️ Nguyên tắc thực hiện
- Chia nhỏ thành **6 Giai đoạn (Phase)** với từng **Task kiểm tra nhỏ**.
- Sau mỗi Task/Giai đoạn, tiến hành kiểm tra trên giao diện thực tế trước khi chuyển sang bước tiếp theo.

---

## 🟢 GIAI ĐOẠN 1: Design System Base & Cyber Dark Theme (CSS Tokens)
- [x] **Task 1.1**: Khởi tạo Bộ Token CSS Theme (Tông màu Dark Base `#060911`, Navy Slate `#0F172A`, các mã màu Neon `#00F0FF`, `#00E676`, `#FFB800`, `#FF2A6D` và Phông chữ Monospace/Sci-Fi).
- [x] **Task 1.2**: Tạo hiệu ứng bề mặt Kính mờ (Glassmorphism), Viền phát sáng vi mô (Neon Border) và Lớp nền Lưới Radar (`background-grid`).
- [x] **Task 1.3**: Tinh chỉnh Nút bấm phong cách Công nghiệp (Industrial Glow Buttons) và Đèn LED báo hiệu trạng thái (Status Badges).
- 🔍 *Kiểm tra Giai đoạn 1*: Khởi chạy Frontend, xác nhận màu nền Dark Theme, viền kính mờ và phông chữ chuẩn hiển thị sắc nét.

---

## 🟢 GIAI ĐOẠN 2: Header Công Nghiệp & Thanh Điều Hướng Navigation
- [x] **Task 2.1**: Thiết kế lại **Top Bar Header** chuẩn GCS (Bổ sung Logo `FPT POLYTECHNIC` + `ALPHA TEAM`, Đồng hồ số real-time `HH:MM:SS ICT`, Thẻ LED Badges kết nối real-time: `WS`, `UAV`, `PLC`, `ROBOT`).
- [x] **Task 2.2**: Thiết kế lại **Tab Navigation Bar** dạng nút nhôm phay (Brushed Metal Active Tabs) phát sáng Cyber Cyan khi chọn tab.
- 🔍 *Kiểm tra Giai đoạn 2*: Chuyển đổi qua lại giữa 4 tab (Kho thông minh, Ground Control Station, Live Map GPS, Split View) mượt mà, hiệu ứng Active rõ ràng.

---

## 🟢 GIAI ĐOẠN 3: Bảng Điều Khiển Drone (Ground Control Station - GCS Dashboard)
- [x] **Task 3.1**: Nâng cấp **HUD Telemetry Panel** (Đồng hồ viễn thám Attitude Roll/Pitch/Yaw, Thủy ngân đo độ cao Laser MTF-02P AGL, Tín hiệu GPS Satellites & Pin).
- [x] **Task 3.2**: Nâng cấp **Step-by-Step Flight Pipeline UI** (Hiển thị 7 bước dạng Card UI phát sáng theo tiến trình `1. ARM` ➔ `7. NORMAL_LANDING`).
- [x] **Task 3.3**: Nâng cấp **Camera Panel & ArUco Vision Overlay** (Khung soi camera GCS + Bounding Box neon phát hiện ArUco marker & chỉ số lệch `offset_x, offset_y`).
- [x] **Task 3.4**: Nâng cấp **Safety & Emergency Controls** (Nút khẩn cấp `FORCE_RTL`, `FORCE_DISARM` màu đỏ Crimson nổi bật có viền bảo vệ).
- 🔍 *Kiểm tra Giai đoạn 3*: Thao tác điều khiển thử 7 bước pipeline, kiểm tra thông số nhảy real-time và hiển thị video stream camera.

---

## 🟢 GIAI ĐOẠN 4: Kho Thông Minh Digital Twin (Smart Intralogistics Panel)
- [x] **Task 4.1**: Thiết kế lại **Storage Slots Grid** dạng khối Kệ kho 3D Glass Card trực quan (Trống: Xám mờ, Có hàng: Xanh Cyan, Đặt trước: Vàng Amber).
- [x] **Task 4.2**: Nâng cấp Bảng điều khiển **PLC S7-1200 & Cửa Hatch** (Công tắc toggle công nghiệp, Đèn LED chuyển động Z-axis nâng/hạ).
- [x] **Task 4.3**: Nâng cấp Bảng điều khiển **Robot Arm (Gắp/Trả sản phẩm)** & Khung soi Camera quét mã vạch QR.
- 🔍 *Kiểm tra Giai đoạn 4*: Kiểm tra tương tác mở cửa Hatch, đổi trạng thái kệ kho và nút điều khiển Robot.

---

## 🟢 GIAI ĐOẠN 5: Bản Đồ Live Map GPS & Quản Lý Đơn Hàng (Leaflet Map & Delivery Requests)
- [x] **Task 5.1**: Áp dụng Dark Theme Map (CartoDB Dark Matter / Stamen Dark) cho bản đồ Leaflet.
- [x] **Task 5.2**: Thiết kế Marker Drone (xoay theo Heading), Trạm Kho Home Base và Đường bay Polyline phát sáng Cyber Cyan.
- [x] **Task 5.3**: Tái cấu trúc Bảng Đơn Hàng (**Delivery Requests Panel**) chuẩn giao diện danh sách điều hành GCS.
- 🔍 *Kiểm tra Giai đoạn 5*: Chọn đơn hàng, theo dõi đường bay và vị trí Drone di chuyển mượt mà trên bản đồ Dark Theme.

---

## 🟢 GIAI ĐOẠN 6: Chế Độ Song Song & Tối Ưu Tổng Thể (Split View & Final Polish)
- [x] **Task 6.1**: Cấu hình chế độ **Split View** (Bản đồ GPS + Telemetry ở nửa trái | Digital Twin Kho + Camera ArUco ở nửa phải).
- [x] **Task 6.2**: Rà soát tối ưu hiệu năng UI, hiệu ứng mượt mà, kiểm tra hiển thị responsive và hoàn tất nghiệm thu toàn bộ Admin Frontend.
- 🔍 *Kiểm tra Giai đoạn 6*: Chạy thử nghiệm End-to-End toàn bộ Admin Dashboard trên tất cả chế độ xem.
