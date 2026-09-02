# BÁO CÁO CHI TIẾT: THIẾT BỊ PHẦN CỨNG & TOÀN BỘ TÍNH NĂNG HỆ THỐNG
## SMART DRONE DELIVERY & INTRALOGISTICS SYSTEM (v3.0)

Tài liệu này cung cấp bảng tra cứu toàn diện về **công dụng, thông số kỹ thuật, cách thức kết nối của từng thiết bị phần cứng** và **toàn bộ những gì hệ thống có thể thực hiện được** trong vận hành thực tế.

---

## MỤC LỤC
1. [Tổng Quan Hệ Thống](#1-tổng-quan-hệ-thống)
2. [Chi Tiết Công Dụng & Chức Năng Của Từng Thiết Bị](#2-chi-tiết-công-dụng--chức-năng-của-từng-thiết-bị)
   - [2.1. Robot Công Nghiệp FAIRINO FR3 (Cobot 6 Trục)](#21-robot-công-nghiệp-fairino-fr3-cobot-6-trục)
   - [2.2. Bộ Điều Khiển Lập Trình PLC Siemens S7-1200](#22-bộ-điều-khiển-lập-trình-plc-siemens-s7-1200)
   - [2.3. Máy Bay Không Người Lái (UAV / Drone Giao Hàng)](#23-máy-bay-không-người-lai-uav--drone-giao-hàng)
   - [2.4. Camera Thị Giác Máy Tính (USB Vision Scanner CAM01)](#24-camera-thị-giác-máy-tính-usb-vision-scanner-cam01)
   - [2.5. Hệ Thống Băng Tải Thông Minh (Conveyor System)](#25-hệ-thống-băng-tải-thông-minh-conveyor-system)
   - [2.6. Trạm Bãi Đáp Drone (Drone Landing Dock N1)](#26-trạm-bãi-đáp-drone-drone-landing-dock-n1)
   - [2.7. Máy Chủ Điều Phối Trung Tâm & Trạm Giám Sát HMI (Backend + Frontend)](#27-máy-chủ-điều-phối-trung-tâm--trạm-giám-sát-hmi)
3. [Hệ Thống Có Thể Làm Được Những Gì? (Năng Lực Vận Hành)](#3-hệ-thống-có-thể-làm-được-những-gì-năng-lực-vận-hành)
   - [Năng lực 1: Xuất kho giao hàng tự động bằng Drone (Outbound Delivery)](#năng-lực-1-xuất-kho-giao-hàng-tự-động-bằng-drone-outbound-delivery)
   - [Năng lực 2: Nhận hàng nhập kho tự động từ Drone (Inbound Pickup)](#năng-lực-2-nhận-hàng-nhập-kho-tự-động-từ-drone-inbound-pickup)
   - [Năng lực 3: Xuất hàng theo hàng đợi ra băng tải cho nhân viên (Staff Outbound)](#năng-lực-3-xuất-hàng-theo-hàng-đợi-ra-băng-tải-cho-nhân-viên-staff-outbound)
   - [Năng lực 4: Nạp hàng chủ động liên tục từ băng tải vào kho (Staff Inbound)](#năng-lực-4-nạp-hàng-chủ-động-liên-tục-từ-băng-tải-vào-kho-staff-inbound)
   - [Năng lực 5: Điều phối hàng đợi thông minh & Phân tách chế độ độc lập](#năng-lực-5-điều-phối-hàng-đợi-thông-minh--phân-tách-chế-độ-độc-lập)
   - [Năng lực 6: Cơ chế liên động an toàn phần cứng (Hardware Safety Interlock)](#năng-lực-6-cơ-chế-liên-động-an-toàn-phần-cứng-hardware-safety-interlock)
   - [Năng lực 7: Thị giác máy tính AI & Truy xuất nguồn gốc kiện hàng](#năng-lực-7-thị-giác-máy-tính-ai--truy-xuất-nguồn-gốc-kiện-hàng)
   - [Năng lực 8: Giám sát Realtime, Điều khiển thủ công & Mô phỏng Digital Twin](#năng-lực-8-giám-sát-realtime-điều-khiển-thủ-công--mô-phỏng-digital-twin)
4. [Bảng Ánh Xạ Giao Tiếp Phần Cứng Toàn Hệ Thống](#4-bảng-ánh-xạ-giao-tiếp-phần-cứng-toàn-hệ-thống)

---

## 1. TỔNG QUAN HỆ THỐNG

Hệ thống **Smart Drone Delivery & Warehouse Intralogistics** là một tổ hợp tự động hóa tích hợp đa ngành (Cơ điện tử, Tự động hóa công nghiệp, IoT, Thị giác máy tính và Robot học). Hệ thống giải quyết trọn vẹn chu trình logistics khép kín:
- **Lưu trữ & Xuất/Nhập hàng hóa tự động**: Quản lý ma trận ô kệ thông minh 9 ô ($A1 \dots C3$).
- **Giao nhận hàng chặng cuối (Last-mile Delivery)**: Sử dụng Drone tự bay giao hàng cho khách hàng và bay về trạm nạp hàng.
- **Tiếp nhận & Phân phối nội bộ (Intralogistics)**: Kết nối kho với nhân viên thông qua băng tải tự động hai chiều.

Toàn bộ quá trình vận hành cơ khí được bảo vệ bằng các rào chắn logic liên động (Safety Interlocks) cấp phần cứng giữa PLC và Robot.

---

## 2. CHI TIẾT CÔNG DỤNG & CHỨC NĂNG CỦA TỪNG THIẾT BỊ

### 2.1. Robot Công Nghiệp FAIRINO FR3 (Cobot 6 Trục)
* **Tên thiết bị**: FAIRINO Collaborative Robot FR3.
* **Firmware / Controller**: Fairino V3.9.21 / Controller FR3 V6.0.
* **Địa chỉ kết nối**: IP `192.168.57.2`, Cổng Socket TCP `8090` (hoặc `9100`).
* **Kịch bản điều khiển**: `code-robot.lua` chạy trực tiếp trên bộ điều khiển robot.

#### Công dụng chính:
1. **Thao tác gắp/đặt sản phẩm vật lý**:
   - Gắp hàng từ các ô lưu trữ ($A1 \dots B3$) và đặt lên bãi đáp Drone $N1$ (Xuất kho Drone).
   - Gắp hàng từ bãi đáp Drone $N1$ và cất vào các ô lưu trữ (Nhập kho Drone).
   - Gắp hàng từ các ô lưu trữ đặt ra vị trí đầu băng tải $O1$ (Xuất kho cho nhân viên).
   - Gắp hàng từ đầu băng tải $O1$ cất vào ô kho (Nhân viên nạp hàng).
2. **Thực thi quỹ đạo an toàn tùy biến**:
   - Chạy các hàm PTP nội suy với chuỗi điểm tiếp cận tránh va quẹt cơ khí: `HOME_A` (tầng A), `HOME_B` (tầng B), `HOME_N1` (trạm Drone), `HOME_O1` (băng tải).
   - Offset tiếp cận lùi $50\text{ mm}$ khi gắp và nhấc cao $50\text{ mm}$ khi thả để tránh quẹt miệng ô.
3. **Liên động an toàn phần cứng với PLC**:
   - Sử dụng các cổng I/O cách ly quang:
     - **`DO0`**: Tín hiệu báo Robot đang ở vị trí **HOME OK** (an toàn cho phép trục Z của PLC di chuyển).
     - **`DO1`**: Xung báo hoàn thành đặt hàng ra băng tải $O1$ để PLC kích chạy động cơ.
     - **`DO2`**: Xung báo hoàn thành cất hàng vào kho từ $O1$.
     - **`DI0`**: Tín hiệu từ PLC yêu cầu Robot về vị trí Home khẩn cấp.
     - **`DI1`**: Tín hiệu từ PLC báo đầu băng tải $O1$ đang trống.
     - **`DI2`**: Tín hiệu từ PLC báo đầu băng tải $O1$ đã có hàng chờ gắp.
4. **Hàm chuyển đổi an toàn logic `SafeSetDO`**:
   - Bù mức đảo logic giữa ngõ ra NPN Sinking của Robot Fairino và ngõ vào DI Sourcing (+24VDC chung 1M) của PLC Siemens S7-1200.

---

### 2.2. Bộ Điều Khiển Lập Trình PLC Siemens S7-1200
* **Tên thiết bị**: Siemens SIMATIC S7-1200 (CPU 1214C DC/DC/DC hoặc tương đương).
* **Địa chỉ kết nối**: IP `192.168.58.10`, Rack 0, Slot 1.
* **Giao thức điều khiển**: Siemens Snap7 Ethernet (Giao thức khối dữ liệu chia sẻ `DB15`).

#### Công dụng chính:
1. **Điều khiển Trục nâng hạ thẳng đứng (Trục Z đa tầng)**:
   - Nhận mã tầng mục tiêu từ Backend qua `DB15.DBW8`:
     - `0`: Tầng an toàn (HOME)
     - `1`: Tầng kệ kho hàng A ($A1, A2, A3$)
     - `2`: Tầng kệ kho hàng B ($B1, B2, B3$)
     - `3`: Tầng bãi đáp Drone $N1$
     - `4`: Tầng đầu băng tải $O1$
   - Chỉ cho phép kích hoạt động cơ trục Z khi phát hiện Robot đang ở vị trí Home (`DO0 == 1`).
   - Phản hồi trạng thái đến tầng an toàn qua bit `DB15.DBX2.7` (`plc_z_in_position`).
2. **Cơ cấu khóa ngàm cơ khí cố định Drone (Drone Clamping)**:
   - Nhận lệnh khóa `DB15.DBX0.0` (`cmd_lock_drone`) $\rightarrow$ Kích xilanh kẹp chặt chân Drone chống trượt/lật cánh khi Robot thao tác.
   - Nhận lệnh mở `DB15.DBX0.1` (`cmd_unlock_drone`) $\rightarrow$ Mở ngàm cho Drone cất cánh.
   - Báo trạng thái kẹp hoàn tất qua `DB15.DBX2.1` (`plc_locked_state`).
3. **Cảm biến quang bãi đáp Drone (Landing Detection)**:
   - Đọc cảm biến tiệm cận quang điện tại mặt bãi đáp $N1$, phát hiện Drone đã hạ cánh $\rightarrow$ Kích bit `DB15.DBX2.0` (`drone_detected`).
4. **Điều khiển Động cơ Băng tải & Cảm biến hàng hóa**:
   - Kích khởi động động cơ băng tải đưa hàng ra cho nhân viên (`DB15.DBX3.2`).
   - Đọc Cảm biến 1 tại đầu $O1$ (`DB15.DBX3.0`) và Cảm biến 2 tại cuối băng tải phía nhân viên (`DB15.DBX3.1`).
   - Đếm số lượng sản phẩm xuất/nhập thực tế qua biến đếm phần cứng `DB15.DBW6`.
5. **Giám sát Dừng khẩn cấp cấp độ phần cứng (Hardware E-Stop)**:
   - Giám sát mạch nút ấn nấm E-Stop vật lý trên tủ điện. Khi kích hoạt, ngắt toàn bộ nguồn động lực và báo bit `DB15.DBX2.6` (`emergency_stop`) về Backend.

---

### 2.3. Máy Bay Không Người Lái (UAV / Drone Giao Hàng)
* **Tên thiết bị / ID**: UAV01, UAV02 (Fleet Management).
* **Bộ điều khiển bay (Flight Controller)**: PX4 Autopilot / MAVLink Protocol.
* **Máy tính nhúng trên thân (Companion Computer)**: Raspberry Pi 5 (IP `192.168.137.88`).
* **Giao tiếp**: MAVLink WebSocket kết nối về trạm mặt đất.

#### Công dụng chính:
1. **Thực hiện nhiệm vụ bay tự động (Autonomous Flight Mission)**:
   - Tự động cất cánh (Auto Takeoff) sau khi hoàn tất nạp hàng tại trạm.
   - Bay theo hành trình tọa độ định vị GPS/RTK đến điểm giao cho khách hàng (`DRONE_EN_ROUTE`).
   - Bay đến vị trí khách hàng để nhận kiện hàng và tự động bay hồi trạm (`DRONE_PICKUP`).
2. **Hạ cánh chính xác xuống bãi đáp trạm (Precision Landing)**:
   - Sử dụng cảm biến quang/laser và camera hạ cánh (IR/Aruco Marker) để đáp chính xác vào tâm bãi đáp $N1$.
3. **Giá mang hàng thông minh (Payload Mechanism)**:
   - Thiết kế khoang chứa kiện hàng tiêu chuẩn, tương thích với giác hút/kẹp của Robot Cobot FR3.
4. **Truyền nhận dữ liệu thời gian thực (Telemetry Streaming)**:
   - Phát realtime phần trăm pin, chế độ bay (AUTO/MANUAL), tốc độ, tọa độ, độ cao và trạng thái mang hàng về giao diện HMI.

---

### 2.4. Camera Thị Giác Máy Tính (USB Vision Scanner CAM01)
* **Tên thiết bị**: USB Digital Vision Camera (CAM01).
* **Vị trí lắp đặt**: Đặt cố định tại góc quan sát quét mã kiện hàng gần vùng thao tác của Robot.
* **Thư viện xử lý**: OpenCV Python (`cv2.QRCodeDetector` + DirectShow API trên Windows).

#### Công dụng chính:
1. **Đối soát mã QR hàng xuất (`QR_VERIFY`)**:
   - Khi Robot vừa gắp sản phẩm ra khỏi ô lưu trữ, đưa kiện hàng qua tầm nhìn camera.
   - Camera tự động giải mã QR và so khớp với `product_id` của đơn hàng trong cơ sở dữ liệu.
   - Ngăn chặn triệt để lỗi gửi sai hàng lên Drone.
2. **Nhận dạng và trích xuất mã hàng nhập (`QR_SCAN`)**:
   - Khi Drone hoặc nhân viên đưa kiện hàng mới vào, camera quét đọc mã định danh thực tế, tạo bản ghi tự động lưu vào CSDL kho.
3. **Live Stream Video Feed**:
   - Truyền luồng video MJPEG thời gian thực lên giao diện điều khiển HMI (`GET /api/inventory/camera-scan/video-feed`) giúp người vận hành quan sát trực quan từ xa.
4. **Quản lý tài nguyên On-Demand**:
   - Tự động bật camera khi cần quét và tự động giải phóng cổng USB (`stop_camera()`) ngay sau khi hoàn thành, chống tràn bộ nhớ và chống xung đột luồng video.

---

### 2.5. Hệ Thống Băng Tải Thông Minh (Conveyor System)
* **Cấu tạo**: Băng tải con lăn/dây đai công nghiệp điều khiển bằng rơ-le/biến tần qua PLC.
* **Cảm biến tích hợp**: 2 mắt cảm biến quang điện (Photocell Sensors).

#### Công dụng chính:
1. **Cầu nối trung chuyển giữa Robot và Nhân viên kho**:
   - Đầu $O1$ (gần Robot): Nơi Robot gắp hàng xuống hoặc lấy hàng lên.
   - Đầu cuối (phía ngoài): Nơi nhân viên đứng nhận hàng xuất hoặc đặt hàng cần nạp.
2. **Tự động kích hoạt hành trình chuyển hàng**:
   - Khi Robot đặt hàng xong tại $O1$ và phát xung `DO1`, PLC tự kích động cơ kéo kiện hàng chạy về phía nhân viên.
   - Khi nhân viên đặt kiện hàng vào, băng tải tự đưa đến đúng cữ $O1$ để Robot đón gắp.
3. **Chống kẹt hàng & Đếm số lượng tự động**:
   - Kết hợp cảm biến đầu và cuối để xác nhận kiện hàng đã rời vị trí trước khi tiến hành chu kỳ tiếp theo, tự động tăng biến đếm `DB15.DBW6`.

---

### 2.6. Trạm Bãi Đáp Drone (Drone Landing Dock N1)
* **Ký hiệu trên hệ thống**: Vị trí tọa độ $N1$.
* **Cấu tạo**: Mặt sàn bãi đáp tích hợp cơ cấu dẫn hướng cơ khí, cảm biến hạ cánh quang điện và ngàm kẹp chân Drone điều khiển khí nén.

#### Công dụng chính:
1. **Tiếp nhận Drone**: Bãi đỗ an toàn cho Drone hạ cánh tiếp tế hoặc nhận hàng.
2. **Khóa cứng cơ khí chống rung lắc**: Ngàm kẹp giữ chặt càng Drone trong lúc Robot vươn tay gắp/thả kiện hàng để bảo vệ an toàn cánh quạt và khung Drone.
3. **Đồng bộ cao độ làm việc**: Kết hợp với Trục Z để nâng toàn bộ cụm bãi đáp đến đúng tầm với tối ưu của tay máy Robot FR3.

---

### 2.7. Máy Chủ Điều Phối Trung Tâm & Trạm Giám Sát HMI
* **Backend Framework**: Python 3.11 + FastAPI + SQLAlchemy Async + Snap7 + Asyncio TCP Socket.
* **Frontend Dashboard**: React 18 + TypeScript + Vite + WebSocket Realtime.

#### Công dụng chính:
1. **Bộ não điều phối nhiệm vụ (Mission Dispatcher)**:
   - Tiếp nhận đơn hàng từ khách hoặc yêu cầu xuất/nhập kho từ nhân viên.
   - Thuật toán quản lý hàng đợi FIFO tự động chọn ô trống, cấp phát Drone phù hợp.
2. **Quản lý máy trạng thái hữu hạn (Finite State Machine - FSM)**:
   - Điều khiển nhịp nhàng các chu kỳ cơ điện tử phức tạp, đồng bộ hóa thời gian thực qua WebSocket.
3. **Giao diện HMI đa phân hệ**:
   - **Màn hình Giám sát Kho Trạm (Dashboard)**: Xem 3D mô phỏng kho 9 ô, trạng thái Drone, tình trạng kết nối từng thiết bị.
   - **Cổng Nhân Viên (Staff Portal)**: Giao diện trực quan chọn ô lấy hàng, chọn chế độ nạp hàng, hiển thị mô phỏng băng tải realtime.
   - **Bảng Điều Khiển Nhanh (Quick Control & Manual Override)**: Cho phép kỹ sư test riêng lẻ từng chuyển động của Trục Z, Kẹp Drone, Tay máy Robot.

---

## 3. HỆ THỐNG CÓ THỂ LÀM ĐƯỢC NHỮNG GÌ? (NĂNG LỰC VẬN HÀNH)

Hệ thống sở hữu **8 năng lực tự động hóa cốt lõi**:

### Năng lực 1: Xuất kho giao hàng tự động bằng Drone (Outbound Delivery)
Hệ thống có khả năng tự động hoàn toàn quy trình xuất một kiện hàng từ kho lên Drone:
1. Tự phát hiện Drone hạ cánh tại bãi đáp $N1$ qua cảm biến quang.
2. PLC tự kích xilanh khóa chặt càng Drone.
3. PLC nâng trục Z đưa ô kho tương ứng về cao độ làm việc.
4. Robot Fairino FR3 vươn tay vào sâu trong kệ gắp kiện hàng ra vị trí an toàn.
5. Camera AI đối soát mã QR của kiện hàng. Nếu đúng hàng, tiếp tục; nếu sai, báo dừng cảnh báo.
6. PLC đưa trục Z đến cao độ bãi đáp $N1$.
7. Robot đặt kiện hàng chính xác vào gá mang hàng trên lưng Drone.
8. Trục Z lùi về Home, PLC mở ngàm kẹp giải phóng Drone.
9. CSDL tự động đánh dấu ô kho vừa xuất thành `EMPTY`.
10. Drone tự động khởi động motor, cất cánh bay đi giao hàng cho khách theo tọa độ GPS.

---

### Năng lực 2: Nhận hàng nhập kho tự động từ Drone (Inbound Pickup)
Quy trình nhập hàng từ bên ngoài về kho thông qua Drone hoàn toàn không cần con người:
1. Drone mang kiện hàng hạ cánh xuống bãi đáp $N1$.
2. PLC khóa kẹp chân Drone cố định.
3. Trục Z nâng bãi đáp lên ngang tầm tay Robot.
4. Robot gắp kiện hàng từ lưng Drone đưa vào vị trí quét.
5. Trục Z hạ về Home, Camera AI tự động quét mã QR để lấy thông tin sản phẩm.
6. Hệ thống tự động tìm kiếm ô còn trống trong ma trận kho ($A1 \dots B3$).
7. Trục Z nâng đến tầng của ô trống đó.
8. Robot đưa hàng vào đặt ngay ngắn trong ô kho.
9. Trục Z về Home an toàn, ngàm mở nhả Drone.
10. CSDL cập nhật ô kho thành `OCCUPIED` gắn với mã sản phẩm và mã QR vừa quét.

---

### Năng lực 3: Xuất hàng theo hàng đợi ra băng tải cho nhân viên (Staff Outbound)
Nhân viên kho có thể thao tác lấy hàng loạt sản phẩm ra băng tải:
- Nhân viên chọn các ô kho cần lấy trên giao diện Staff Portal (ví dụ: chọn $A1, A3, B2$).
- Hệ thống tự động xếp vào hàng đợi xuất (Outbound Queue).
- Lần lượt từng ô:
  - PLC nâng Z đến tầng của ô $\rightarrow$ Robot gắp sản phẩm ra $\rightarrow$ Đặt xuống vị trí $O1$ trên đầu băng tải.
  - Robot kích xung phần cứng `DO1` sang PLC.
  - PLC nhận `DO1` tự động chạy băng tải đưa sản phẩm về phía nhân viên đứng chờ.
  - CSDL tự giải phóng ô kho thành `EMPTY`.
- Tự động tiếp tục cho đến khi xuất hết danh sách yêu cầu.

---

### Năng lực 4: Nạp hàng chủ động liên tục từ băng tải vào kho (Staff Inbound)
Cho phép nhân viên nạp bổ sung hàng loạt kiện hàng mới vào kho:
- Nhân viên bật chế độ nạp trên HMI và chỉ việc đặt lần lượt kiện hàng lên đầu băng tải $O1$.
- Cảm biến đầu băng tải phát hiện có hàng $\rightarrow$ PLC kích chân `DI2` báo Robot.
- Hệ thống tự tìm ô trống khả dụng $\rightarrow$ Robot gắp hàng tại $O1$.
- Kiện hàng đi qua camera quét mã QR tự động.
- Trục Z nâng đến tầng ô trống $\rightarrow$ Robot cất hàng vào kệ $\rightarrow$ Kích xung `DO2` xác nhận.
- CSDL tự động lưu trữ thông tin kiện hàng.
- Hệ thống chạy liên tục cho đến khi nạp đầy 6 ô hoạt động hoặc khi nhân viên bấm kết thúc.

---

### Năng lực 5: Điều phối hàng đợi thông minh & Phân tách chế độ độc lập
- **Chuyển đổi phân hệ an toàn (`SystemModeManager`)**:
  - Hỗ trợ 2 phân hệ độc lập: **`START KHO TRẠM` (Trạm Drone)** và **`CHẾ ĐỘ NHÂN VIÊN` (Staff Operation)**.
  - Khi nhân viên thao tác lấy/thêm hàng, hệ thống **tự động cô lập và tạm dừng hàng đợi Drone**, đảm bảo không xảy ra xung đột tài nguyên Robot hoặc va chạm cơ khí.
- **Hàng đợi FIFO tự động**:
  - Các đơn hàng mới tự động xếp hàng (`QUEUED`). Khi trạm rảnh, hệ thống tự động gọi nhiệm vụ tiếp theo (`auto_dispatch_next_mission`).
  - Hỗ trợ tính năng Tạm dừng (`Pause Auto`) và Tiếp tục hàng đợi (`Resume Queue`) linh hoạt.

---

### Năng lực 6: Cơ chế liên động an toàn phần cứng (Hardware Safety Interlock)
Được thiết kế theo tiêu chuẩn an toàn công nghiệp chống va chạm:
- **Khóa chéo Trục Z - Robot**: Robot chỉ cần rời vị trí Home thì ngõ ra `DO0 = 0`, PLC lập tức khóa điện động cơ trục Z, loại bỏ nguy cơ trục Z di chuyển đè gãy tay máy Robot.
- **Khóa chéo Trục Z - Vị trí an toàn**: Robot chỉ vươn tay gắp khi nhận được tín hiệu `DB15.DBX2.7 = 1` báo trục Z đã dừng đúng tầng.
- **Khóa chéo Drone**: Robot tuyệt đối không vươn tay ra bãi đáp $N1$ nếu chưa có xác nhận ngàm kẹp đã khóa cứng chân Drone (`DB15.DBX2.1 = 1`).
- **Nút E-Stop toàn diện**: Khi nhấn E-Stop tại tủ điện hoặc trên giao diện HMI, toàn bộ chuyển động Robot, Trục Z và Băng tải lập tức dừng tức thì trong vòng $50\text{ ms}$.

---

### Năng lực 7: Thị giác máy tính AI & Truy xuất nguồn gốc kiện hàng
- Tự động nhận diện và đọc mã QR không cần người cầm máy quét thủ công.
- Đối soát tự động 2 chiều (Verify khi xuất và Cataloging khi nhập).
- Lưu vết toàn bộ lịch sử: Kiện hàng nào, mã QR gì, nằm ở ô kho nào, do Drone nào chở, xuất/nhập vào thời điểm nào.
- Hiển thị Live Video Feed trực tiếp trên trình duyệt Web.

---

### Năng lực 8: Giám sát Realtime, Điều khiển thủ công & Mô phỏng Digital Twin
- **Bản sao số (Digital Twin / Simulator Mode)**:
  - Cho phép chạy mô phỏng toàn bộ logic hệ thống $100\%$ mượt mà trên máy tính phát triển mà không cần cắm nối phần cứng thật.
- **Giám sát Realtime qua WebSocket**:
  - Giao diện Dashboard cập nhật trạng thái ô kho, trạng thái Drone, tiến độ từng bước của Robot từng giây.
- **Điều khiển can thiệp thủ công (Manual Override)**:
  - Kỹ sư vận hành có thể điều khiển riêng lẻ: Bật/tắt ngàm kẹp, nâng/hạ trục Z từng tầng, đưa Robot về Home, chạy thử băng tải, bật/tắt luồng camera để phục vụ bảo trì, căn chỉnh cơ khí.

---

## 4. BẢNG ÁNH XẠ GIAO TIẾP PHẦN CỨNG TOÀN HỆ THỐNG

### 4.1. Bảng Bit & Word PLC Siemens S7-1200 (`DB15`)
| Địa chỉ DB15 | Tên Biến (Tag) | Chiều | Thiết bị liên quan | Chức năng chi tiết |
|:---:|:---:|:---:|:---:|:---|
| **`DB15.DBX0.0`** | `cmd_lock_drone` | Backend $\rightarrow$ PLC | Ngàm kẹp bãi đáp $N1$ | Kích đóng xilanh khóa chân Drone |
| **`DB15.DBX0.1`** | `cmd_unlock_drone` | Backend $\rightarrow$ PLC | Ngàm kẹp bãi đáp $N1$ | Mở xilanh giải phóng chân Drone |
| **`DB15.DBX0.2`** | `cmd_target_z` | Backend $\rightarrow$ PLC | Động cơ Trục Z | Lệnh kích hoạt chạy trục Z đến tầng `DBW8` |
| **`DB15.DBX0.5`** | `cmd_start_plc` | Backend $\rightarrow$ PLC | Toàn hệ thống trạm | Khởi động hệ thống PLC sẵn sàng hoạt động |
| **`DB15.DBX0.6`** | `cmd_reset_plc` | Backend $\rightarrow$ PLC | Toàn hệ thống trạm | Lệnh xóa lỗi / Reset sau sự cố |
| **`DB15.DBX0.7`** | `watchdog_heartbeat` | Backend $\rightarrow$ PLC | PLC CPU | Nhịp tim Watchdog giám sát kết nối (1 Hz) |
| **`DB15.DBX1.0`** | `cmd_staff_mode_enable` | Backend $\rightarrow$ PLC | Băng tải | Kích hoạt phân hệ Nhân viên kho |
| **`DB15.DBX1.1`** | `cmd_staff_outbound_start` | Backend $\rightarrow$ PLC | Băng tải | Bắt đầu chu trình xuất hàng ra băng tải |
| **`DB15.DBX1.3`** | `cmd_staff_inbound_start` | Backend $\rightarrow$ PLC | Băng tải | Bắt đầu chu trình nạp hàng từ băng tải |
| **`DB15.DBW4`** | `staff_target_count` | Backend $\rightarrow$ PLC | Băng tải | Cài đặt số lượng kiện hàng yêu cầu |
| **`DB15.DBW8`** | `target_z_level` | Backend $\rightarrow$ PLC | Động cơ Trục Z | Mã tầng mục tiêu (0: Home, 1: Hàng A, 2: Hàng B, 3: N1, 4: O1) |
| **`DB15.DBX2.0`** | `drone_detected` | PLC $\rightarrow$ Backend | Cảm biến bãi đáp $N1$ | Báo Drone đã hạ cánh chạm sàn bãi đáp |
| **`DB15.DBX2.1`** | `plc_locked_state` | PLC $\rightarrow$ Backend | Ngàm kẹp bãi đáp $N1$ | Báo trạng thái ngàm kẹp đã khóa an toàn |
| **`DB15.DBX2.6`** | `emergency_stop` | PLC $\rightarrow$ Backend | Nút E-Stop tủ điện | Trạng thái nút dừng khẩn cấp được kích hoạt |
| **`DB15.DBX2.7`** | `plc_z_in_position` | PLC $\rightarrow$ Backend | Trục Z | **Báo trục Z đã đến đúng tầng, sẵn sàng cho Robot** |
| **`DB15.DBX3.0`** | `sensor_conveyor_head` | PLC $\rightarrow$ Backend | Cảm biến băng tải | Cảm biến 1: Vị trí đầu $O1$ (nơi Robot gắp) |
| **`DB15.DBX3.1`** | `sensor_conveyor_end` | PLC $\rightarrow$ Backend | Cảm biến băng tải | Cảm biến 2: Vị trí cuối (nơi Nhân viên đứng) |
| **`DB15.DBX3.2`** | `conveyor_running` | PLC $\rightarrow$ Backend | Động cơ băng tải | Báo động cơ băng tải đang quay |
| **`DB15.DBW6`** | `staff_current_count` | PLC $\rightarrow$ Backend | Băng tải | Số lượng kiện hàng thực tế đã đếm qua cảm biến |

---

### 4.2. Bảng I/O Phần Cứng Robot FAIRINO FR3
| Cổng I/O | Kiểu cổng | Tên tín hiệu | Thiết bị kết nối | Mục đích sử dụng |
|:---:|:---:|:---:|:---:|:---|
| **`DO0`** | Digital Output (NPN) | `HOME_OK` | Ngõ vào DI của PLC | Báo PLC: Robot đang ở Home an toàn (cho phép trục Z chạy) |
| **`DO1`** | Digital Output (NPN) | `OUTBOUND_PULSE` | Ngõ vào DI của PLC | Xung báo Robot đã đặt hàng lên $O1$ $\rightarrow$ PLC kích băng tải chạy |
| **`DO2`** | Digital Output (NPN) | `INBOUND_PULSE` | Ngõ vào DI của PLC | Xung báo Robot đã cất xong hàng từ $O1$ vào ô kho $\rightarrow$ PLC đếm nạp |
| **`DI0`** | Digital Input | `CMD_HOME` | Ngõ ra DO của PLC | Lệnh từ PLC ép Robot di chuyển về vị trí Home |
| **`DI1`** | Digital Input | `O1_EMPTY` | Ngõ ra DO của PLC | Tín hiệu báo đầu băng tải $O1$ đang trống |
| **`DI2`** | Digital Input | `O1_HAS_ITEM` | Ngõ ra DO của PLC | Tín hiệu báo đầu băng tải $O1$ đã có kiện hàng chờ gắp |

---

### 4.3. Bảng Lệnh Socket TCP Backend $\leftrightarrow$ Robot (Port 8090)
| Lệnh Gửi Đi | Tham Số | Phản Hồi Từ Robot | Ý Nghĩa Chức Năng |
|:---|:---:|:---|:---|
| `MOVE_HOME` | - | `SUCCESS MOVE_HOME` | Đưa Robot về vị trí Home an toàn thẳng qua p1, p2, p3 |
| `PICK` | `<slot>` (VD: `A1`, `N1`, `O1`) | `SUCCESS PICK <slot>` | Thực hiện quỹ đạo tiếp cận và gắp hàng tại ô chỉ định |
| `STORE` | `<slot>` (VD: `B2`, `N1`, `O1`) | `SUCCESS STORE <slot>` | Thực hiện quỹ đạo tiếp cận và đặt hàng vào ô chỉ định |
| `OUTBOUND_CYCLE` | `<slot>` | `SUCCESS OUTBOUND <slot>` | Chu trình xuất tự động: Ô kho $\rightarrow$ Home $\rightarrow$ $O1$ $\rightarrow$ Xung `DO1` |
| `INBOUND_CYCLE` | `<slot>` | `SUCCESS INBOUND <slot>` | Chu trình nạp tự động: $O1$ $\rightarrow$ Home $\rightarrow$ Ô kho $\rightarrow$ Xung `DO2` |
| `STATUS` | - | `STATE:... BUSY:... POS:...` | Truy vấn trạng thái hoạt động hiện tại của Robot |
| `STOP` / `ESTOP` | - | `STOP SUCCESS STATE:ESTOP` | Dừng khẩn cấp mọi chuyển động của Robot ngay tức thì |
| `RESET` | - | `RESET SUCCESS STATE:IDLE` | Xóa trạng thái lỗi sau dừng khẩn cấp đưa về sẵn sàng |
