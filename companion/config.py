"""
Drone Delivery Companion — Raspberry Pi 5 configuration.

Hardware:
    Raspberry Pi 5
    Pixhawk 6C
    USB Camera / CSI Camera

Connection:
    Laptop
        |
        SSH
        |
    Raspberry Pi 5
        |
        MAVLink UART
        |
    Pixhawk 6C
"""

import os
import platform


# ===========================================================================
# Network
# ===========================================================================

DRONE_ID = os.getenv(
    "DRONE_ID",
    "drone-01"
)

SERVER_IP = os.getenv(
    "SERVER_IP",
    "192.168.137.1"
)

SERVER_PORT = int(
    os.getenv(
        "SERVER_PORT",
        "8000"
    )
)

WS_URL = (
    f"ws://{SERVER_IP}:{SERVER_PORT}"
    f"/ws/drone/{DRONE_ID}"
)


# ===========================================================================
# MAVLink PX4 Pixhawk 6C
# ===========================================================================

MAVLINK_DEVICE = os.getenv(
    "MAVLINK_DEVICE",
    "/dev/ttyAMA0"
)

MAVLINK_BAUD = int(
    os.getenv(
        "MAVLINK_BAUD",
        "921600"
    )
)

MAVLINK_TARGET_SYSTEM = 1
MAVLINK_TARGET_COMPONENT = 1


MAVLINK_RECONNECT_DELAY_SEC = 5.0
MAVLINK_HEARTBEAT_TIMEOUT = 30
MAVLINK_STREAM_RATE_HZ = int(
    os.getenv(
        "MAVLINK_STREAM_RATE_HZ",
        "10"
    )
)



# ===========================================================================
# Camera
# ===========================================================================

# webcam:
#       USB camera
#
# picamera2:
#       Raspberry Pi CSI Camera

CAMERA_BACKEND = os.getenv(
    "CAMERA_BACKEND",
    "webcam"
)


# USB camera:
# /dev/video0 -> index 0
# /dev/video1 -> secondary stream
CAMERA_WEBCAM_INDEX = int(
    os.getenv(
        "CAMERA_WEBCAM_INDEX",
        "0"
    )
)


CAMERA_WIDTH = int(
    os.getenv(
        "CAMERA_WIDTH",
        "640"
    )
)


CAMERA_HEIGHT = int(
    os.getenv(
        "CAMERA_HEIGHT",
        "480"
    )
)


CAMERA_FPS = int(
    os.getenv(
        "CAMERA_FPS",
        "30"
    )
)



# ===========================================================================
# ArUco Precision Landing
# ===========================================================================

# OpenCV dictionary
#
# phải giống marker được in

ARUCO_DICTIONARY = os.getenv(
    "ARUCO_DICTIONARY",
    "DICT_5X5_50"
)


# Marker thực tế:
# 15cm x 15cm

ARUCO_MARKER_SIZE_M = 0.15


# ID marker dùng landing

ARUCO_MARKER_ID = 0


ARUCO_CAMERA_FPS = 30


# Tần suất gửi ArUco detection result về backend (giây)
CAMERA_ARUCO_SEND_INTERVAL_SEC = 2.0



# ===========================================================================
# Mission
# ===========================================================================

TAKEOFF_ALTITUDE_M = float(
    os.getenv(
        "TAKEOFF_ALTITUDE_M",
        "1.75"
    )
)


RTL_ALTITUDE_M = float(
    os.getenv(
        "RTL_ALTITUDE_M",
        "6.0"
    )
)


DESCEND_ALTITUDE_M = float(
    os.getenv(
        "DESCEND_ALTITUDE_M",
        "1.0"
    )
)


NAV_ACCEPTANCE_RADIUS_M = 2.0

# Giây chờ sau khi đạt độ cao cất cánh trước khi switch sang AUTO.LOITER
LOITER_SWITCH_DELAY_SEC = float(
    os.getenv(
        "LOITER_SWITCH_DELAY_SEC",
        "0.5"
    )
)

# Tốc độ hành trình DO_REPOSITION (m/s). -1 = dùng giá trị mặc định PX4 (MPC_XY_VEL_MAX)
NAV_CRUISE_SPEED_MS = float(
    os.getenv(
        "NAV_CRUISE_SPEED_MS",
        "2.0"
    )
)

# Timeout an toàn cất cánh: nếu không đạt độ cao mục tiêu trong thời gian này, hủy lệnh
TAKEOFF_TIMEOUT_SEC = float(
    os.getenv(
        "TAKEOFF_TIMEOUT_SEC",
        "15.0"
    )
)

# Timeout hành trình DO_REPOSITION: log cảnh báo nếu không đến đích sau thời gian này
NAV_ARRIVAL_TIMEOUT_SEC = float(
    os.getenv(
        "NAV_ARRIVAL_TIMEOUT_SEC",
        "60.0"
    )
)


LANDING_SEARCH_TIMEOUT_SEC = 30.0

# Thời gian tối đa chấp nhận không nhận DISTANCE_SENSOR trước khi đánh dấu rangefinder invalid
# QUAN TRỌNG: EKF2_BARO_CTRL=0 — Không có Baro fallback. Nếu sensor mất > 0.5s, hệ thống cảnh báo ngay
RANGEFINDER_STALE_TIMEOUT_SEC = float(
    os.getenv(
        "RANGEFINDER_STALE_TIMEOUT_SEC",
        "0.5"
    )
)

# Lưu ý tham số PX4 liên quan:
#   COM_OF_LOSS_T    = 1.5   (không phải 0.5 — dung sai cho Linux jitter trên Raspberry Pi 5)
#   EKF2_HGT_REF     = 2    (Range sensor — MTF-02P là nguồn độ cao chính)
#   EKF2_BARO_CTRL   = 0    (Tắt Baro fusion — tránh drift nhiệt Pixhawk)
#   MPC_Z_VEL_MAX_UP = 1.0  (đủ cho Vz=0.6m/s trong OFFBOARD takeoff)



# ===========================================================================
# Logging
# ===========================================================================

LOG_FILE = os.getenv(
    "LOG_FILE",
    "/var/log/drone-companion.log"
)

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO"
)



# ===========================================================================
# Telemetry
# ===========================================================================

TELEMETRY_INTERVAL_SEC = 2.0

MAVLINK_POLL_RATE_HZ = 20



# ===========================================================================
# Websocket
# ===========================================================================

WS_RECONNECT_DELAY_SEC = 3.0

WS_MAX_RECONNECT_ATTEMPTS = 0



# ===========================================================================
# System
# ===========================================================================

IS_PI = True

IS_WINDOWS = (
    platform.system()
    ==
    "Windows"
)