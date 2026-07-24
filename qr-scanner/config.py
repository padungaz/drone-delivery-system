"""
QR Scanner Station — Warehouse Computer Configuration.

Ứng dụng chạy trên máy tính đặt tại kho hàng.
Camera quét mã QR sản phẩm và gửi dữ liệu tới Backend server qua LAN.

Cấu hình qua biến môi trường hoặc file .env
"""

import os

from dotenv import load_dotenv

load_dotenv()


# ===========================================================================
# Backend Server Connection
# ===========================================================================

SERVER_IP = os.getenv("SERVER_IP", "192.168.137.1")

SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# HTTP endpoint để gửi dữ liệu QR
SCAN_API_URL = f"http://{SERVER_IP}:{SERVER_PORT}/storage/scan"

# HTTP endpoint để lấy trạng thái kho
STORAGE_API_URL = f"http://{SERVER_IP}:{SERVER_PORT}/storage"

# WebSocket endpoint để nhận real-time updates
WS_URL = f"ws://{SERVER_IP}:{SERVER_PORT}/ws/client"


# ===========================================================================
# Camera
# ===========================================================================

# USB camera index (0 = default, 1 = secondary, ...)
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))

CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))

CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))

CAMERA_FPS = int(os.getenv("CAMERA_FPS", "30"))


# ===========================================================================
# QR Scanner Behavior
# ===========================================================================

# Thời gian tối thiểu giữa 2 lần gửi cùng 1 QR code (giây)
# Tránh quét trùng khi QR vẫn nằm trước camera
SCAN_DEBOUNCE_SEC = float(os.getenv("SCAN_DEBOUNCE_SEC", "5.0"))

# Thời gian chờ trước khi cho phép quét lại bất kỳ QR nào (giây)
# Reset debounce cache sau khoảng thời gian này
SCAN_CACHE_TTL_SEC = float(os.getenv("SCAN_CACHE_TTL_SEC", "30.0"))


# ===========================================================================
# WebSocket
# ===========================================================================

WS_RECONNECT_DELAY_SEC = float(os.getenv("WS_RECONNECT_DELAY_SEC", "3.0"))


# ===========================================================================
# Display
# ===========================================================================

# Hiển thị cửa sổ camera preview (True/False)
SHOW_PREVIEW = os.getenv("SHOW_PREVIEW", "true").lower() in ("true", "1", "yes")
