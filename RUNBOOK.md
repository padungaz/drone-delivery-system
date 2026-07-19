# RUNBOOK — Vận hành & Gỡ lỗi

Tài liệu này tập trung vào các thao tác vận hành hàng ngày (Operations), kiểm tra lỗi (Troubleshooting), và danh sách kiểm tra an toàn trước chuyến bay (Pre-flight checklist).

---

## 1. Pre-Flight Checklist (Kiểm tra trước khi bay)

Trước khi thực hiện bất kỳ chuyến bay tự động nào, bắt buộc phải hoàn thành các bước kiểm tra sau:

- [ ] **Mạng & Máy chủ:** Backend đang chạy (`http://192.168.137.1:8000/health` OK).
- [ ] **Kết nối Pi:** Ping `192.168.137.139` thành công, có thể SSH vào hệ thống.
- [ ] **Companion App:** Service `drone-companion` đang chạy không báo lỗi.
- [ ] **Pixhawk MAVLink:** Pi nhận được heartbeat của PX4 (`journalctl -u drone-companion` hiển thị OK).
- [ ] **Telemetry WebSocket:** Admin Dashboard hiển thị thông số theo thời gian thực (update mỗi 2 giây).
- [ ] **Định vị & Pin:** GPS báo fix ≥ 6 vệ tinh. Dung lượng pin (Battery) > 50%.
- [ ] **Hạ cánh:** ArUco markers đặt đúng vị trí (Pickup và Drop) không bị che khuất.
- [ ] **An toàn (Failsafe):** Nút FORCE RTL trên giao diện đã được kiểm tra và sẵn sàng. Không gian bay trống (clear).

---

## 2. Kiểm tra Kết nối Thủ công

Nếu bạn nghi ngờ có vấn đề về kết nối giữa các thành phần, sử dụng các tập lệnh Python (snippet) sau để kiểm tra:

### 2.1 Test MAVLink (Pixhawk ↔ Pi)
Chạy trên Raspberry Pi:
```bash
python3 -c "
from pymavlink import mavutil
conn = mavutil.mavlink_connection('/dev/ttyAMA0', baud=921600)
print('Waiting for heartbeat...')
conn.wait_heartbeat(timeout=15)
print('PX4 connected — system:', conn.target_system)
"
```

### 2.2 Test WebSocket (Pi ↔ Backend)
Chạy trên Laptop hoặc Pi:
```bash
python3 -c "
import asyncio, websockets
async def test():
    url = 'ws://192.168.137.1:8000/ws/drone/drone-01'
    async with websockets.connect(url) as ws:
        print('Connected to', url)
asyncio.run(test())
"
```

### 2.3 Test Camera & Nhận diện ArUco
Yêu cầu: Backend và Companion đang chạy.

**Qua giao diện Frontend (Admin):**
1. Mở `http://192.168.137.1:5173`.
2. Nhấn nút **📷 Test Camera** trong panel "Camera & ArUco".
3. Trạng thái chuyển từ 🔴 Camera OFF → 🟢 Camera ON.
4. Đưa mã ArUco (DICT_4X4_50, ID=0) ra trước camera USB, theo dõi tọa độ Offset/Center.
5. Nhấn **⏹ Stop Camera** khi hoàn thành.

**Qua API thủ công:**
```bash
# Bật camera
curl -X POST http://192.168.137.1:8000/camera/start?drone_id=drone-01

# Tắt camera
curl -X POST http://192.168.137.1:8000/camera/stop?drone_id=drone-01
```

---

## 3. Quản lý Service trên Raspberry Pi

Quản lý tiến trình `drone-companion` (dùng systemd):

```bash
# Bắt đầu, dừng, hoặc khởi động lại
sudo systemctl start drone-companion
sudo systemctl stop drone-companion
sudo systemctl restart drone-companion

# Xem trạng thái
sudo systemctl status drone-companion

# Xem log theo thời gian thực
journalctl -u drone-companion -f

# Xem 100 dòng log gần nhất
journalctl -u drone-companion -n 100
```

---

## 4. Xử lý Sự cố (Troubleshooting)

### 4.1 Không nhận MAVLink / Timeout
**Triệu chứng:**
```
[WARNING] MAVLink connection failed (attempt 1) — retrying in 5s
```
**Khắc phục:**
- Kiểm tra dây cáp UART (chân TX của Pixhawk phải nối với chân RX của Pi và ngược lại).
- Kiểm tra tốc độ baudrate trong QGroundControl: `SER_TEL2_BAUD = 921600`.
- Xác minh quyền truy cập cổng Serial: chạy lệnh `groups rpi5`, nếu không có `dialout`, chạy `sudo usermod -aG dialout rpi5` rồi đăng nhập lại.
- Xác nhận Bluetooth đã bị vô hiệu hóa (`dtoverlay=disable-bt` trong `/boot/firmware/config.txt`) để cổng `/dev/ttyAMA0` khả dụng.

### 4.2 Lỗi Mất kết nối WebSocket
**Triệu chứng:**
```
[WARNING] WebSocket connect failed (attempt 1): ... — retrying in 3s
```
**Khắc phục:**
- Kiểm tra Backend Server trên Laptop có đang chạy hay không.
- Xác nhận địa chỉ IP của Laptop là `192.168.137.1` và Ping từ Pi có phản hồi.
- Đảm bảo tường lửa (Firewall) trên Windows/Linux không chặn cổng 8000 mạng LAN.
- Kiểm tra lại biến môi trường `SERVER_IP` trong tệp `/opt/drone-delivery-system/companion/.env`.

### 4.3 Raspberry Pi không có IP mong muốn (192.168.137.139)
**Khắc phục:**
- Raspberry Pi 5 Bookworm sử dụng `NetworkManager` (không phải `dhcpcd`). Dùng `sudo nmcli con show` để tìm tên kết nối (ví dụ: `preconfigured`).
- Cấu hình lại IP tĩnh:
  ```bash
  sudo nmcli con mod "preconfigured" ipv4.addresses 192.168.137.139/24 ipv4.method manual
  sudo nmcli con up "preconfigured"
  ```

### 4.4 Lỗi ghi log file bị Permission Denied
**Khắc phục:**
Tạo file log và cấp quyền cho user `rpi5`:
```bash
sudo touch /var/log/drone-companion.log
sudo chown rpi5:rpi5 /var/log/drone-companion.log
```
