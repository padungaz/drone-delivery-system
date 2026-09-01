# BẢNG ÁNH XẠ BỘ NHỚ PLC SIEMENS S7-1200 (DB15 I/O HANDBOOK)
### Dự án: Trạm Sạc & Giao Nhận Drone Tự Động Kết Hợp Kho Thông Minh (Drone Delivery & Smart Warehouse System)

---

## 1. THÔNG SỐ KẾT NỐI MẠNG & THIẾT BỊ
* **Thiết bị**: Siemens SIMATIC S7-1200 CPU 1214C / 1215C DC/DC/DC
* **Địa chỉ IP mặc định**: `192.168.58.10`
* **Cổng Profinet**: `102` (ISO-on-TCP)
* **Giao thức Backend**: `python-snap7` (S7 Protocol)
* **Khối dữ liệu Data Block**: `DB15` (Non-optimized block access để truy cập theo Offset cố định)
* **Chiều dài khối dữ liệu**: `10 Bytes` (Bytes 0 .. 9)
* **Chu kỳ quét / Watchdog**: Đọc trạng thái mỗi `100ms - 150ms`; Toggle nhịp tim Watchdog mỗi `1.0s`.

---

## 2. BẢNG TỔNG HỢP VÙNG NHỚ DB15 (BYTE & WORD OVERVIEW)

| Địa chỉ Offset | Kiểu dữ liệu | Hướng truyền nhận | Tên phân hệ | Chức năng chính |
|:---:|:---:|:---:|:---:|:---|
| **`DB15.DBB0`** | `BYTE` (8 Bits) | Backend $\rightarrow$ PLC | Trạm & Drone | Các bit lệnh điều khiển trạm, khóa drone, thang nâng Z và lệnh hệ thống |
| **`DB15.DBB1`** | `BYTE` (8 Bits) | Backend $\rightarrow$ PLC | Phân hệ Nhân viên | Các bit lệnh điều khiển chế độ nhân viên và chu trình băng tải |
| **`DB15.DBB2`** | `BYTE` (8 Bits) | PLC $\rightarrow$ Backend | Trạng thái Trạm | Phản hồi cảm biến tiếp đất, trạng thái kẹp, vị trí trục Z và E-Stop |
| **`DB15.DBB3`** | `BYTE` (8 Bits) | PLC $\rightarrow$ Backend | Trạng thái Băng tải | Phản hồi cảm biến quang băng tải, trạng thái chạy và cờ hoàn tất |
| **`DB15.DBW4`** | `INT` (16 Bits) | Backend $\rightarrow$ PLC | Đếm số lượng | Số lượng kiện hàng nhân viên yêu cầu xuất/nhập |
| **`DB15.DBW6`** | `INT` (16 Bits) | PLC $\rightarrow$ Backend | Đếm số lượng | Số lượng kiện hàng thực tế đã đi qua cảm biến băng tải |
| **`DB15.DBW8`** | `INT` (16 Bits) | Backend $\rightarrow$ PLC | Điều khiển Trục Z | Mã tầng mục tiêu cho trục Z nâng/hạ (0=Home, 1=Hàng A, 2=Hàng B, 3=N1, 4=O1) |

---

## 3. CHI TIẾT TỪNG BIT TRONG VÙNG NHỚ DB15

### 3.1. BYTE 0: Lệnh Điều Khiển Trạm & Drone (Backend $\rightarrow$ PLC)
*Ghi chú: Backend ghi xung (Pulse) lên `True`, sau khi PLC nhận lệnh và bắt đầu chu trình, Backend hoặc PLC tự động hạ về `False`.*

| Địa chỉ Bit | Tên Tag (Code) | Kiểu | Mô tả chức năng | Ghi chú vận hành |
|:---:|:---:|:---:|:---|:---|
| **`DB15.DBX0.0`** | `cmd_lock_drone` | `BOOL` | Yêu cầu PLC đóng cơ cấu ngàm kẹp khóa cố định Drone | Kích hoạt khi Drone đã đáp lên Pad N1 |
| **`DB15.DBX0.1`** | `cmd_unlock_drone` | `BOOL` | Yêu cầu PLC mở ngàm kẹp giải phóng Drone | Kích hoạt trước khi Drone cất cánh |
| **`DB15.DBX0.2`** | `cmd_target_z` | `BOOL` | **Lệnh kích hoạt chạy trục Z đến tầng mục tiêu DBW8** | **Backend set 1 để PLC kích chạy Z; khi DB15.DBX2.7 (in_pos)=1 thì Backend tắt về 0** |
| **`DB15.DBX0.3`** | *Reserved* | `BOOL` | *Dự phòng* | Không dùng |
| **`DB15.DBX0.4`** | `cmd_stop_plc` | `BOOL` | Dừng chu trình làm việc của trạm | Tạm dừng hoạt động trạm |
| **`DB15.DBX0.5`** | `cmd_start_plc` | `BOOL` | Khởi động / Cho phép hệ thống PLC hoạt động | Lệnh bật hệ thống chính |
| **`DB15.DBX0.6`** | `cmd_reset_plc` | `BOOL` | Xóa lỗi (Reset Error) và khôi phục trạng thái sẵn sàng | Xóa cờ lỗi sau khi xử lý sự cố |
| **`DB15.DBX0.7`** | `watchdog_heartbeat` | `BOOL` | Xung nhịp tim Watchdog từ Backend | Backend đảo bit mỗi 1.0 giây để báo kết nối còn sống |

---

### 3.2. BYTE 1: Lệnh Chế Độ Nhân Viên & Băng Tải (Backend $\rightarrow$ PLC)

| Địa chỉ Bit | Tên Tag (Code) | Kiểu | Mô tả chức năng | Ghi chú vận hành |
|:---:|:---:|:---:|:---|:---|
| **`DB15.DBX1.0`** | `cmd_staff_mode_enable` | `BOOL` | Kích hoạt Chế độ Nhân viên (1 = Staff Mode, 0 = Station Auto) | Khóa tạm thời điều phối Drone để ưu tiên kho |
| **`DB15.DBX1.1`** | `cmd_staff_outbound_start` | `BOOL` | Khởi động chu trình Xuất hàng ra Băng tải | Robot lấy từ kho ra O1 $\rightarrow$ Băng tải chạy đến cuối |
| **`DB15.DBX1.2`** | `cmd_staff_outbound_cancel`| `BOOL` | Hủy chu trình Xuất hàng ra Băng tải | Dừng cưỡng bức xuất hàng |
| **`DB15.DBX1.3`** | `cmd_staff_inbound_start` | `BOOL` | Khởi động chu trình Thêm hàng từ O1 vào Kho | Nhân viên đặt hàng tại O1 $\rightarrow$ Robot cất vào ô |
| **`DB15.DBX1.4`** | `cmd_staff_inbound_stop` | `BOOL` | Dừng chu trình Thêm hàng | Kết thúc phiên thêm hàng |
| **`DB15.DBX1.5`** | *Reserved* | `BOOL` | Dự phòng (PLC tự quản lý động cơ băng tải nội bộ) | Không can thiệp từ xa |
| **`DB15.DBX1.6`** | *Reserved* | `BOOL` | Dự phòng (PLC tự quản lý động cơ băng tải nội bộ) | Không can thiệp từ xa |
| **`DB15.DBX1.7`** | *Reserved* | `BOOL` | Dự phòng | Mặc định 0 |

---

### 3.3. BYTE 2: Trạng Thái Trạm & Trục Z (PLC $\rightarrow$ Backend)
*Ghi chú: Vùng nhớ chỉ đọc (Read-only) từ phía Backend để giám sát và làm điều kiện chuyển bước FSM.*

| Địa chỉ Bit | Tên Tag (Code) | Kiểu | Mô tả chức năng | Ghi chú vận hành |
|:---:|:---:|:---:|:---|:---|
| **`DB15.DBX2.0`** | `drone_detected` | `BOOL` | Cảm biến phát hiện Drone đã tiếp đất trên bãi đáp Pad N1 | 1 = Đã có Drone, 0 = Bãi đáp trống |
| **`DB15.DBX2.1`** | `plc_locked_state` | `BOOL` | Trạng thái cơ cấu kẹp khóa Drone | 1 = Đã khóa chặt Drone, 0 = Đã mở khóa |
| **`DB15.DBX2.2`** | *Reserved* | `BOOL` | *Dự phòng (Đã loại bỏ — Thay thế bằng DB15.DBX2.7 & DBW8)* | Không dùng |
| **`DB15.DBX2.3`** | *Reserved* | `BOOL` | *Dự phòng (Đã loại bỏ — Thay thế bằng DB15.DBX2.7 & DBW8)* | Không dùng |
| **`DB15.DBX2.4`** | `plc_on` | `BOOL` | Hệ thống PLC đang chạy và sẵn sàng nhận lệnh | Trạng thái RUN của trạm |
| **`DB15.DBX2.5`** | `plc_error` | `BOOL` | PLC phát hiện sự cố / lỗi vận hành | 1 = Báo lỗi |
| **`DB15.DBX2.6`** | `emergency_stop` | `BOOL` | Nút dừng khẩn cấp E-Stop vật lý bị nhấn | 1 = Dừng khẩn cấp, khóa mọi chuyển động |
| **`DB15.DBX2.7`** | `plc_z_in_position` | `BOOL` | **Trục Z đã đến tầng mục tiêu và đứng yên sẵn sàng** | **Điều kiện an toàn tuyệt đối cho Robot bắt đầu gắp/thả** |

---

### 3.4. BYTE 3: Trạng Thái Băng Tải & Phân Hệ Nhân Viên (PLC $\rightarrow$ Backend)

| Địa chỉ Bit | Tên Tag (Code) | Kiểu | Mô tả chức năng | Ghi chú vận hành |
|:---:|:---:|:---:|:---|:---|
| **`DB15.DBX3.0`** | `sensor_conveyor_head` | `BOOL` | Cảm biến 1: Đầu băng tải (Vị trí O1 làm việc của Robot) | 1 = Có kiện hàng tại O1 |
| **`DB15.DBX3.1`** | `sensor_conveyor_end` | `BOOL` | Cảm biến 2: Cuối băng tải (Vị trí lấy hàng của Nhân viên) | 1 = Có kiện hàng tại cuối băng tải |
| **`DB15.DBX3.2`** | `conveyor_running` | `BOOL` | Trạng thái Động cơ Băng tải đang quay | 1 = Băng tải RUN, 0 = Băng tải STOP |
| **`DB15.DBX3.3`** | `staff_outbound_busy` | `BOOL` | PLC đang bận chu trình xuất hàng ra băng tải | Chống xung đột lệnh |
| **`DB15.DBX3.4`** | `staff_outbound_done` | `BOOL` | PLC báo đã xuất xong toàn bộ số lượng hàng ra băng tải | Hoàn thành chu trình xuất |
| **`DB15.DBX3.5`** | `staff_inbound_busy` | `BOOL` | PLC đang bận chu trình nạp hàng từ O1 vào kho | Chống xung đột lệnh |
| **`DB15.DBX3.6`** | `staff_inbound_done` | `BOOL` | PLC báo đã hoàn tất phiên nạp hàng | Hoàn thành chu trình nhập |
| **`DB15.DBX3.7`** | `staff_mode_active` | `BOOL` | PLC xác nhận đang ở Chế độ Nhân viên (Staff Mode) | Đã khóa chế độ tự động kho |

---

### 3.5. CÁC VÙNG NHỚ WORD (INT16 / 2 BYTES)

#### 1. `DB15.DBW4` (Bytes 4–5): `staff_target_count`
- **Kiểu dữ liệu**: `INT16` (Signed 16-bit Integer)
- **Hướng**: Backend $\rightarrow$ PLC
- **Chức năng**: Số lượng kiện hàng Backend yêu cầu PLC xuất hoặc nhập trong phiên làm việc của nhân viên.

#### 2. `DB15.DBW6` (Bytes 6–7): `staff_current_count`
- **Kiểu dữ liệu**: `INT16` (Signed 16-bit Integer)
- **Hướng**: PLC $\rightarrow$ Backend
- **Chức năng**: Số lượng kiện hàng thực tế mà PLC đã đếm được thông qua cảm biến quang khi hàng trôi qua băng tải.

#### 3. `DB15.DBW8` (Bytes 8–9): `target_z_level`
- **Kiểu dữ liệu**: `INT16` (Signed 16-bit Integer)
- **Hướng**: Backend $\rightarrow$ PLC
- **Chức năng**: Mã định danh tầng độ cao mục tiêu cho động cơ trục Z (nâng/hạ thang).
- **Bảng mã quy ước tầng Z**:

| Mã số (Int) | Tên Tầng Quy Ước | Vị trí / Ô Kho tương ứng | Ý nghĩa nghiệp vụ |
|:---:|:---:|:---:|:---|
| **`0`** | `Z_LEVEL_HOME` | Vị trí HOME / Đáy trạm | Vị trí nghỉ an toàn, vị trí Drone cất/hạ cánh |
| **`1`** | `Z_LEVEL_ROW_A` | Hàng kho A (`A1`, `A2`, `A3`) | Trục Z nâng đến độ cao hàng A để Robot thao tác ô A |
| **`2`** | `Z_LEVEL_ROW_B` | Hàng kho B (`B1`, `B2`, `B3`) | Trục Z nâng đến độ cao hàng B để Robot thao tác ô B |
| **`3`** | `Z_LEVEL_DOCK_N` | Bãi đáp Drone (`N1`) | Trục Z đưa bệ đỡ lên khớp với tầm với Drone N1 |
| **`4`** | `Z_LEVEL_CONVEYOR` | Đầu băng tải (`O1`) | Trục Z đưa vị trí làm việc ngang mặt băng tải xuất/nhập |

---

## 4. QUY TẮC LIÊN ĐỘNG AN TOÀN PHẦN CỨNG (SAFETY INTERLOCK)

```
                       ┌─────────────────────────┐
                       │   ROBOT FAIRINO FR3     │
                       └────────────┬────────────┘
                                    │ Tín hiệu DO0:
                                    │ 1 = ROBOT Ở HOME AN TOÀN
                                    │ 0 = ROBOT RỜI HOME
                                    ▼
                       ┌─────────────────────────┐
                       │  PLC SIEMENS S7-1200    │
                       │  (Khóa liên động trục Z)│
                       └────────────┬────────────┘
                                    │
               ┌────────────────────┴────────────────────┐
               │                                         │
        DO0 == 0 (Nguy hiểm)                      DO0 == 1 (An toàn)
               │                                         │
               ▼                                         ▼
   [KHÓA CỨNG TRỤC Z]                        [CHO PHÉP TRỤC Z CHẠY]
   Trục Z tuyệt đối không                   PLC điều khiển trục Z đến
   được nâng/hạ để chống va                 tầng mục tiêu ghi trong DBW8.
   chạm gãy tay Robot.                                   │
                                                         ▼
                                             Khi Z đến đúng tầng:
                                             PLC set DB15.DBX2.7 = 1
                                                         │
                                                         ▼
                                             [ROBOT BẮT ĐẦU GẮP/THẢ]
                                             Backend ra lệnh Robot vươn
                                             tay gắp/cất kiện hàng.
```

1. **Điều kiện cho Trục Z chạy**:
   - Robot bắt buộc phải ở vị trí HOME an toàn. Tín hiệu phần cứng từ ngõ ra số của Robot **`DO0 = 1`** (đấu nối vào ngõ vào số của PLC, ví dụ `I0.0`).
   - PLC đọc thấy `DO0 == 1` thì mới cấp điện/phát xung cho động cơ trục Z di chuyển theo mã tầng `DB15.DBW8`.
   - Nếu `DO0 == 0`, PLC khóa trục Z ngay lập tức.
2. **Điều kiện cho Robot vươn tay vào ô kho / bãi đáp**:
   - Backend chỉ gửi lệnh `PICK` hoặc `STORE` xuống Robot khi bit **`DB15.DBX2.7 (plc_z_in_position) == True`**.
   - Khi Robot đang di chuyển ngoài vị trí Home, `DO0` tự động ngắt về `0`.

### 4.2. Giao thức Kích Hoạt & Bắt Tay Lệnh Trục Z (Strobe Handshake DBX0.2 & DBX2.7)
Để PLC phân biệt rõ ràng khi nào Backend yêu cầu chạy Z:
1. **Backend ghi mã tầng**: Ghi giá trị tầng mục tiêu (0, 1, 2, 3, 4) vào **`DB15.DBW8`** (`target_z_level`).
2. **Backend kích hoạt lệnh**: Bật bit **`DB15.DBX0.2 = 1`** (`cmd_target_z = True`).
3. **PLC thực thi**:
   - PLC phát hiện `DB15.DBX0.2 == 1` và `DO0 == 1` (Robot Home).
   - PLC kích hoạt biến tần / servo điều khiển động cơ trục Z di chuyển đến độ cao tương ứng với `DB15.DBW8`.
   - Trong quá trình trục Z đang di chuyển, PLC duy trì **`DB15.DBX2.7 = 0`** (`plc_z_in_position = False`).
4. **PLC báo hoàn thành**:
   - Khi trục Z đã đến đúng tầng mục tiêu và dừng êm ổn định, PLC bật **`DB15.DBX2.7 = 1`** (`plc_z_in_position = True`).
5. **Backend tắt lệnh kích hoạt**:
   - Backend nhận được `DB15.DBX2.7 == 1`, lập tức tắt bit **`DB15.DBX0.2 = 0`** (`cmd_target_z = False`).
   - Chu trình bắt tay kết thúc an toàn, Robot bắt đầu gắp/thả kiện hàng!

---

## 5. TÀI LIỆU THAM KHẢO CODE
- Module quản lý PLC Backend: [plc_manager.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/services/plc_manager.py)
- Schema dữ liệu trạng thái PLC: [schemas.py](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/backend/app/models/schemas.py)
- Giao diện giám sát & điều khiển thủ công PLC: [PLCMonitor.tsx](file:///c:/Users/MSI%20GAMING/Desktop/drone-delivery-system/frontend/src/components/plc/PLCMonitor.tsx)
