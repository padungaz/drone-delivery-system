"""
CameraService — USB camera + ArUco detection background thread.

Headless mode: không dùng cv2.imshow, chỉ detect + gửi kết quả qua callback.
Dùng cho test camera từ frontend và chuẩn bị dữ liệu cho MAVLink LANDING_TARGET.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

import cv2
import cv2.aruco as aruco

import config

logger = logging.getLogger(__name__)

# ArUco dictionary mapping
ARUCO_DICT_MAP = {
    "DICT_4X4_50": aruco.DICT_4X4_50,
    "DICT_4X4_100": aruco.DICT_4X4_100,
    "DICT_5X5_50": aruco.DICT_5X5_50,
    "DICT_5X5_100": aruco.DICT_5X5_100,
    "DICT_6X6_50": aruco.DICT_6X6_50,
    "DICT_6X6_250": aruco.DICT_6X6_250,
}


@dataclass
class ArucoResult:
    """Result of a single ArUco detection cycle."""
    aruco_detected: bool = False
    marker_id: int = -1
    center_x: int = 0
    center_y: int = 0
    offset_x: int = 0
    offset_y: int = 0
    image_width: int = 0
    image_height: int = 0
    timestamp: str = ""


class CameraService:
    """Manages USB camera + background ArUco detection thread."""

    def __init__(
        self,
        on_camera_status: Optional[Callable[[str, str], None]] = None,
        on_aruco_detection: Optional[Callable[[dict], None]] = None,
    ):
        """
        Args:
            on_camera_status: callback(status, device) — called when camera state changes
            on_aruco_detection: callback(payload) — called every 2s with ArUco results
        """
        self._on_camera_status = on_camera_status
        self._on_aruco_detection = on_aruco_detection

        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._status = "OFF"  # "OFF" | "ON" | "ERROR"
        self._device = ""
        self._last_result = ArucoResult()

        # ArUco detector
        dict_id = ARUCO_DICT_MAP.get(config.ARUCO_DICTIONARY, aruco.DICT_4X4_50)
        self._aruco_dict = aruco.getPredefinedDictionary(dict_id)
        self._aruco_params = aruco.DetectorParameters()
        if hasattr(aruco, "ArucoDetector"):
            self._detector = aruco.ArucoDetector(self._aruco_dict, self._aruco_params)
        else:
            self._detector = None

    @property
    def status(self) -> str:
        return self._status

    @property
    def device(self) -> str:
        return self._device

    @property
    def last_result(self) -> ArucoResult:
        return self._last_result

    def start(self) -> bool:
        """Open camera and start background ArUco detection thread."""
        if self._status == "ON":
            logger.warning("[CAMERA] Camera already running")
            return True

        camera_index = config.CAMERA_WEBCAM_INDEX
        self._device = f"/dev/video{camera_index}"

        logger.info("[CAMERA] Starting camera...")
        logger.info("[CAMERA] Device: %s", self._device)

        try:
            self._cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)

            if not self._cap.isOpened():
                logger.error("[CAMERA] Failed to open camera %s", self._device)
                self._status = "ERROR"
                self._notify_status()
                return False

            # Set resolution and FPS
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            self._cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)

            actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self._cap.get(cv2.CAP_PROP_FPS)

            logger.info("[CAMERA] Resolution: %dx%d", actual_w, actual_h)
            logger.info("[CAMERA] FPS: %.0f", actual_fps)
            logger.info("[CAMERA] ArUco dictionary: %s", config.ARUCO_DICTIONARY)
            logger.info("[CAMERA] Camera started successfully")

            self._status = "ON"
            self._notify_status()

            # Start background detection thread
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._detection_loop,
                name="aruco-detection",
                daemon=True,
            )
            self._thread.start()

            return True

        except Exception as exc:
            logger.error("[CAMERA] Failed to open camera: %s", exc)
            self._status = "ERROR"
            self._notify_status()
            return False

    def stop(self) -> None:
        """Stop camera and detection thread."""
        if self._status == "OFF":
            return

        logger.info("[CAMERA] Stopping camera...")

        # Signal thread to stop
        self._stop_event.set()

        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None

        # Release camera
        if self._cap:
            self._cap.release()
            self._cap = None

        self._status = "OFF"
        self._last_result = ArucoResult()
        self._notify_status()
        logger.info("[CAMERA] Camera stopped")

    def _notify_status(self) -> None:
        """Call the camera status callback."""
        if self._on_camera_status:
            try:
                self._on_camera_status(self._status, self._device)
            except Exception as exc:
                logger.error("[CAMERA] Status callback error: %s", exc)

    def _notify_aruco(self, payload: dict) -> None:
        """Call the ArUco detection callback."""
        if self._on_aruco_detection:
            try:
                self._on_aruco_detection(payload)
            except Exception as exc:
                logger.error("[CAMERA] ArUco callback error: %s", exc)

    def _detection_loop(self) -> None:
        """Background thread: capture frames → detect ArUco → send every 2s."""
        logger.info("[CAMERA] ArUco detection thread started")

        send_interval = config.CAMERA_ARUCO_SEND_INTERVAL_SEC
        last_send_time = 0.0
        latest_result = ArucoResult()

        while not self._stop_event.is_set():
            if self._cap is None or not self._cap.isOpened():
                logger.error("[CAMERA] Camera lost — stopping thread")
                self._status = "ERROR"
                self._notify_status()
                break

            ret, frame = self._cap.read()
            if not ret:
                # Transient read failure — skip frame
                time.sleep(0.05)
                continue

            # Detect ArUco markers
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if self._detector:
                corners, ids, _ = self._detector.detectMarkers(gray)
            else:
                corners, ids, _ = aruco.detectMarkers(
                    gray, self._aruco_dict, parameters=self._aruco_params
                )

            h, w = frame.shape[:2]
            cx, cy = w // 2, h // 2
            now_str = datetime.now(timezone.utc).isoformat()

            if ids is not None and len(ids) > 0:
                # Find target marker (prefer config.ARUCO_MARKER_ID)
                target_idx = None
                for i, mid in enumerate(ids.flatten()):
                    if mid == config.ARUCO_MARKER_ID:
                        target_idx = i
                        break

                # Fallback: use first detected marker
                if target_idx is None:
                    target_idx = 0

                c = corners[target_idx][0]
                mx = int(sum(p[0] for p in c) / 4)
                my = int(sum(p[1] for p in c) / 4)

                latest_result = ArucoResult(
                    aruco_detected=True,
                    marker_id=int(ids[target_idx][0]),
                    center_x=mx,
                    center_y=my,
                    offset_x=mx - cx,
                    offset_y=my - cy,
                    image_width=w,
                    image_height=h,
                    timestamp=now_str,
                )
            else:
                latest_result = ArucoResult(
                    aruco_detected=False,
                    timestamp=now_str,
                )

            self._last_result = latest_result

            # Send result every CAMERA_ARUCO_SEND_INTERVAL_SEC
            now = time.time()
            if now - last_send_time >= send_interval:
                last_send_time = now

                if latest_result.aruco_detected:
                    payload = {
                        "aruco_detected": True,
                        "marker_id": latest_result.marker_id,
                        "center_x": latest_result.center_x,
                        "center_y": latest_result.center_y,
                        "offset_x": latest_result.offset_x,
                        "offset_y": latest_result.offset_y,
                        "image_width": latest_result.image_width,
                        "image_height": latest_result.image_height,
                        "timestamp": latest_result.timestamp,
                    }
                    logger.info(
                        "[CAMERA] ArUco detected — ID:%d dx:%d dy:%d",
                        latest_result.marker_id,
                        latest_result.offset_x,
                        latest_result.offset_y,
                    )
                else:
                    payload = {
                        "aruco_detected": False,
                        "timestamp": latest_result.timestamp,
                    }
                    logger.info("[CAMERA] No ArUco detected")

                self._notify_aruco(payload)

            # Throttle to avoid 100% CPU
            time.sleep(0.03)

        logger.info("[CAMERA] ArUco detection thread stopped")
