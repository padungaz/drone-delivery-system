# Cấu hình PX4 & Pixhawk 6C

Tài liệu này lưu trữ các cấu hình phần cứng, tham số PX4 (parameters), và cách giao tiếp MAVLink với Raspberry Pi Companion.

---

## 1. Sơ đồ kết nối phần cứng (Wiring)

```
Pixhawk 6C (TELEM1)       Raspberry Pi 5
───────────────────       ────────────────
  TX  (pin 2)  ──────►    GPIO15 / RXD (pin 10)
  RX  (pin 3)  ◄──────    GPIO14 / TXD (pin 8)
  GND (pin 6)  ────────   GND          (pin 6)
  5V  (pin 1)  ──────►    (Không bắt buộc nếu Pi dùng nguồn riêng)
```
*(Lưu ý: Chân TX của Pixhawk phải nối vào chân RX của Pi, và ngược lại).*

---

## 2. PX4 Parameters

Áp dụng các tham số sau qua phần mềm **QGroundControl** hoặc chạy `param set` trực tiếp qua MAVLink console.

### MAVLink (Cổng TELEM1)
| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `MAV_0_CONFIG` | `101` | Dùng cổng TELEM1 |
| `MAV_0_MODE` | `2` | Chế độ Onboard (Companion Computer) |
| `MAV_0_RATE` | `1200` | Stream rate (bytes/s) |
| `SER_TEL1_BAUD` | `57600` | Tốc độ Baud (Baud rate) |

### State Estimator (EKF2)
| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `EKF2_EN` | `1` | Bật EKF2 |
| `EKF2_AID_MASK` | `24` | Kết hợp GPS (1) + Vision Position (16) = 17, dùng 24 cho GPS+EV+flow |
| `EKF2_HGT_MODE` | `2` | Dùng Range sensor (đo khoảng cách khi hạ cánh) |
| `EKF2_REQ_NSATS`| `6` | Số lượng vệ tinh tối thiểu |

### Navigation & Mission
| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `MIS_TAKEOFF_ALT` | `10` | Độ cao cất cánh mặc định (m) |
| `NAV_ACC_RAD` | `2` | Bán kính chấp nhận khi đến Waypoint (m) |
| `RTL_RETURN_ALT` | `30` | Độ cao bay khi quay về điểm Home (m) |
| `RTL_DESCEND_ALT`| `10` | Độ cao hạ xuống khi đến điểm Home (m) |

### Precision Landing (Hạ cánh chính xác ArUco)
| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `PLD_HACC_RAD` | `0.2` | Sai số ngang cho phép (m) |
| `PLD_MAX_SRCH` | `3` | Số lần tối đa tìm kiếm marker |
| `PLD_SRCH_ALT` | `10` | Độ cao tìm kiếm (m) |
| `PLD_SRCH_TOUT`| `10` | Thời gian timeout tìm kiếm (s) |
| `LNDMC_ALT_GND` | `2` | Khoảng cách bị ảnh hưởng hiệu ứng mặt đất (m) |
| `LNDMC_XY_VEL_MAX`| `1.5` | Vận tốc ngang tối đa khi hạ cánh (m/s) |
| `LNDMC_Z_VEL_MAX` | `0.25`| Tốc độ hạ cánh tối đa (m/s) |

### Safety / Failsafe
| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `COM_DISARM_LAND` | `2` | Thời gian tự động Disarm sau khi hạ cánh (s) |
| `COM_DL_LOSS_T` | `10` | Timeout mất kết nối datalink (s) |
| `COM_OBC_LOSS_T` | `5` | Timeout mất kết nối với Raspberry Pi Companion (s) |

---

## 3. MAVLink Messages

**Raspberry Pi đọc (subscribe tại 20Hz):**
- `GLOBAL_POSITION_INT` (lat, lon, relative_alt)
- `VFR_HUD` (vận tốc đất, góc hướng)
- `SYS_STATUS` (dung lượng pin còn lại)
- `ATTITUDE` (góc roll, pitch, yaw)
- `GPS_RAW_INT` (số vệ tinh, loại fix)

**Raspberry Pi gửi (publish):**
- `LANDING_TARGET` (để hỗ trợ ArUco precision landing)
- `COMMAND_LONG` (điều khiển arm, takeoff, goto, land, RTL)
- `SET_POSITION_TARGET_GLOBAL_INT` (điều hướng waypoint)

---

## 4. Script nạp thông số tự động (apply_params.sh)

Lưu file bash sau trên Companion để cấu hình nhanh PX4:

```bash
#!/bin/bash
PARAMS=(
  "MAV_0_CONFIG 101"
  "MAV_0_MODE 2"
  "MAV_0_RATE 1200"
  "SER_TEL1_BAUD 57600"
  "EKF2_EN 1"
  "EKF2_AID_MASK 24"
  "EKF2_HGT_MODE 2"
  "EKF2_REQ_NSATS 6"
  "EKF2_GPS_CTRL 7"
  "EKF2_RNG_CTRL 1"
  "PLD_HACC_RAD 0.2"
  "PLD_MAX_SRCH 3"
  "PLD_SRCH_ALT 10"
  "PLD_SRCH_TOUT 10"
  "LNDMC_ALT_GND 2"
  "LNDMC_XY_VEL_MAX 1.5"
  "LNDMC_Z_VEL_MAX 0.25"
  "MIS_TAKEOFF_ALT 10"
  "NAV_ACC_RAD 2"
  "RTL_RETURN_ALT 30"
  "RTL_DESCEND_ALT 10"
  "COM_DISARM_LAND 2"
  "COM_DL_LOSS_T 10"
  "COM_OBC_LOSS_T 5"
  "BAT_LOW_THR 0.15"
  "BAT_CRIT_THR 0.07"
)

for p in "${PARAMS[@]}"; do
  echo "param set $p"
done
echo "param save"
echo "reboot"
```
