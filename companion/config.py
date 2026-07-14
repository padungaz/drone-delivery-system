"""
Companion computer configuration.

RUN_MODE:
  "sim" — PC development (mô phỏng Pi, không cần hardware)
  "pi"  — Raspberry Pi 5 production (CSI camera + UART)

Trên máy tính để chạy mô phỏng: giữ RUN_MODE = "sim" và để picamera2/commented
Trong Raspberry Pi thật: đổi RUN_MODE = "pi" và bật picamera2 trong requirements.txt
"""

import platform

# ---------------------------------------------------------------------------
# Chọn chế độ chạy — đổi "sim" → "pi" khi deploy lên Raspberry Pi
# ---------------------------------------------------------------------------
RUN_MODE = "sim"

# ---------------------------------------------------------------------------
# Network (dùng chung)
# ---------------------------------------------------------------------------
DRONE_ID = "drone-01"
SERVER_PORT = 8000

# ---------------------------------------------------------------------------
# Sim mode — chạy trên PC Windows/Linux
# ---------------------------------------------------------------------------
if RUN_MODE == "sim":
    # Backend trên cùng máy → 127.0.0.1; backend trên máy khác → 192.168.2.28
    SERVER_IP = "127.0.0.1"

    # MAVLink: "mock" = mô phỏng hoàn toàn | "sitl" = PX4 SITL qua UDP
    MAVLINK_BACKEND = "serial"
    MAVLINK_SITL_URI = "udp:127.0.0.1:14540"
    MAVLINK_DEVICE = "COM12"  # Mô phỏng — không dùng trong mock mode
    MAVLINK_BAUD = 57600

    # Camera: "webcam" | "synthetic" (tự render ArUco test)
    CAMERA_BACKEND = "webcam"
    CAMERA_WEBCAM_INDEX = 1
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480

    LOG_FILE = ""
    LOG_LEVEL = "INFO"

# ---------------------------------------------------------------------------
# Pi mode — Raspberry Pi 5 + Pixhawk 6C
# ---------------------------------------------------------------------------
else:
    SERVER_IP = "192.168.2.28"

    MAVLINK_BACKEND = "serial"
    MAVLINK_DEVICE = "/dev/ttyAMA0"
    MAVLINK_BAUD = 57600

    CAMERA_BACKEND = "csi"

    LOG_FILE = "/var/log/drone-companion.log"
    LOG_LEVEL = "INFO"

WS_URL = f"ws://{SERVER_IP}:{SERVER_PORT}/ws/drone/{DRONE_ID}"

# ---------------------------------------------------------------------------
# MAVLink target
# ---------------------------------------------------------------------------
MAVLINK_TARGET_SYSTEM = 1
MAVLINK_TARGET_COMPONENT = 1

# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------
TELEMETRY_INTERVAL_SEC = 2.0
MAVLINK_POLL_RATE_HZ = 20

# ---------------------------------------------------------------------------
# Mission parameters
# ---------------------------------------------------------------------------
TAKEOFF_ALTITUDE_M = 10.0
RTL_ALTITUDE_M = 30.0
DESCEND_ALTITUDE_M = 10.0
NAV_ACCEPTANCE_RADIUS_M = 2.0
LANDING_SEARCH_TIMEOUT_SEC = 30.0

# Sim mock: tọa độ gốc cho mô phỏng GPS (Hà Nội mẫu)
SIM_HOME_LAT = 21.0285
SIM_HOME_LON = 105.8542

# ---------------------------------------------------------------------------
# ArUco
# ---------------------------------------------------------------------------
ARUCO_DICTIONARY = "DICT_4X4_50"
ARUCO_MARKER_SIZE_M = 0.15
ARUCO_MARKER_ID = 0
ARUCO_CAMERA_FPS = 30

# ---------------------------------------------------------------------------
# WebSocket reconnect
# ---------------------------------------------------------------------------
WS_RECONNECT_DELAY_SEC = 3.0
WS_MAX_RECONNECT_ATTEMPTS = 0  # 0 = infinite

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
IS_SIM = RUN_MODE == "sim"
IS_PI = RUN_MODE == "pi"
IS_WINDOWS = platform.system() == "Windows"
