# """
# Drone Delivery Companion — Raspberry Pi 5 configuration.

# Cấu hình được đọc từ environment variables (file .env hoặc export shell).
# Xem .env.example để biết danh sách biến cần thiết.

# Deployment: Raspberry Pi 5 + Pixhawk 6C (MAVLink UART)
# Connection:  Laptop → VS Code Remote SSH → Raspberry Pi 5 → MAVLink → Pixhawk 6C
# """

# import os
# import platform

# # ---------------------------------------------------------------------------
# # Network — đọc từ env, fallback về LAN defaults
# # ---------------------------------------------------------------------------
# DRONE_ID    = os.getenv("DRONE_ID",    "drone-01")
# SERVER_IP   = os.getenv("SERVER_IP",   "192.168.137.1")
# SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# WS_URL = f"ws://{SERVER_IP}:{SERVER_PORT}/ws/drone/{DRONE_ID}"

# # ---------------------------------------------------------------------------
# # MAVLink — UART connection to Pixhawk 6C
# #   /dev/ttyAMA0 → Pi GPIO UART (TELEM1 port)
# #   /dev/ttyUSB0 → USB-Serial adapter
# # ---------------------------------------------------------------------------
# MAVLINK_DEVICE = os.getenv("MAVLINK_DEVICE", "/dev/ttyAMA0")
# MAVLINK_BAUD   = int(os.getenv("MAVLINK_BAUD", "57600"))

# MAVLINK_TARGET_SYSTEM    = 1
# MAVLINK_TARGET_COMPONENT = 1

# # MAVLink reconnect
# MAVLINK_RECONNECT_DELAY_SEC = 5.0
# MAVLINK_HEARTBEAT_TIMEOUT   = 30

# # ---------------------------------------------------------------------------
# # Camera — CSI camera via picamera2 on Raspberry Pi 5
# # ---------------------------------------------------------------------------
# CAMERA_BACKEND      = os.getenv("CAMERA_BACKEND", "webcam")
# CAMERA_WEBCAM_INDEX = int(os.getenv("CAMERA_WEBCAM_INDEX", "1"))
# CAMERA_WIDTH        = 640
# CAMERA_HEIGHT       = 480

# # ---------------------------------------------------------------------------
# # Logging
# # ---------------------------------------------------------------------------
# LOG_FILE  = os.getenv("LOG_FILE",  "/var/log/drone-companion.log")
# LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# # ---------------------------------------------------------------------------
# # Telemetry
# # ---------------------------------------------------------------------------
# TELEMETRY_INTERVAL_SEC = 2.0
# MAVLINK_POLL_RATE_HZ   = 20

# # ---------------------------------------------------------------------------
# # Mission parameters
# # ---------------------------------------------------------------------------
# TAKEOFF_ALTITUDE_M        = float(os.getenv("TAKEOFF_ALTITUDE_M",  "10.0"))
# RTL_ALTITUDE_M            = float(os.getenv("RTL_ALTITUDE_M",      "30.0"))
# DESCEND_ALTITUDE_M        = float(os.getenv("DESCEND_ALTITUDE_M",  "10.0"))
# NAV_ACCEPTANCE_RADIUS_M   = 2.0
# LANDING_SEARCH_TIMEOUT_SEC = 30.0

# # ---------------------------------------------------------------------------
# # ArUco precision landing
# # ---------------------------------------------------------------------------
# ARUCO_DICTIONARY    = "DICT_4X4_50"
# ARUCO_MARKER_SIZE_M = 0.15
# ARUCO_MARKER_ID     = 0
# ARUCO_CAMERA_FPS    = 30

# # ---------------------------------------------------------------------------
# # WebSocket reconnect
# # ---------------------------------------------------------------------------
# WS_RECONNECT_DELAY_SEC     = 3.0
# WS_MAX_RECONNECT_ATTEMPTS  = 0   # 0 = infinite

# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------
# IS_PI      = True
# IS_SIM     = False
# IS_WINDOWS = platform.system() == "Windows"   # False on Pi, kept for compat


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
        "57600"
    )
)

MAVLINK_TARGET_SYSTEM = 1
MAVLINK_TARGET_COMPONENT = 1


MAVLINK_RECONNECT_DELAY_SEC = 5.0
MAVLINK_HEARTBEAT_TIMEOUT = 30



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

ARUCO_DICTIONARY = "DICT_4X4_50"


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
        "10.0"
    )
)


RTL_ALTITUDE_M = float(
    os.getenv(
        "RTL_ALTITUDE_M",
        "30.0"
    )
)


DESCEND_ALTITUDE_M = float(
    os.getenv(
        "DESCEND_ALTITUDE_M",
        "10.0"
    )
)


NAV_ACCEPTANCE_RADIUS_M = 2.0


LANDING_SEARCH_TIMEOUT_SEC = 30.0



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

IS_SIM = False

IS_WINDOWS = (
    platform.system()
    ==
    "Windows"
)