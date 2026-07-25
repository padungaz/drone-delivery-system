import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

import config

logger = logging.getLogger(__name__)

ARUCO_DICT_MAP = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
    "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
    "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
}


@dataclass
class MarkerPose:
    detected: bool = False
    marker_id: int = -1
    dx: float = 0.0
    dy: float = 0.0
    distance: float = 0.0
    angle_x: float = 0.0
    angle_y: float = 0.0


class ArucoLandingService:
    """ArUco marker detection and LANDING_TARGET pose estimation with background threading."""

    def __init__(self):
        dict_id = ARUCO_DICT_MAP.get(config.ARUCO_DICTIONARY, cv2.aruco.DICT_4X4_50)
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        self.camera_matrix: Optional[np.ndarray] = None
        self.dist_coeffs: Optional[np.ndarray] = None
        self._camera = None                          # Picamera2 instance (CSI)
        self._webcam_cap: Optional[cv2.VideoCapture] = None  # OpenCV capture (USB webcam)
        self._camera_backend = "none"                # "csi" | "webcam" | "none"
        self._last_pose = MarkerPose()
        self._last_detected_pose = MarkerPose()

        # Threading support
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def init_camera(self) -> bool:
        self.stop()

        initialized = False
        backend = config.CAMERA_BACKEND

        if backend == "csi":
            # ── CSI camera via picamera2 (Raspberry Pi) ──
            try:
                # pyrefly: ignore [missing-import]
                from picamera2 import Picamera2

                self._camera = Picamera2()
                config_cam = self._camera.create_preview_configuration(
                    main={"size": (config.CAMERA_WIDTH, config.CAMERA_HEIGHT), "format": "RGB888"}
                )
                self._camera.configure(config_cam)
                self._camera.start()
                self._camera_backend = "csi"
                self._init_camera_matrix(config.CAMERA_WIDTH, config.CAMERA_HEIGHT)
                logger.info("CSI camera initialized (%dx%d)", config.CAMERA_WIDTH, config.CAMERA_HEIGHT)
                initialized = True
            except ImportError:
                logger.warning("picamera2 not available — CSI camera cannot be used")
            except Exception as exc:
                logger.error("CSI camera init failed: %s", exc)

        elif backend == "webcam":
            # ── USB webcam via OpenCV VideoCapture (V4L2) ──
            camera_index = config.CAMERA_WEBCAM_INDEX
            device_name = f"/dev/video{camera_index}"
            logger.info("Opening USB webcam %s for ArUco landing...", device_name)

            try:
                if config.IS_WINDOWS:
                    cap = cv2.VideoCapture(camera_index)
                else:
                    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)

                if not cap.isOpened():
                    logger.error("Failed to open USB webcam %s", device_name)
                else:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
                    cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)

                    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    actual_fps = cap.get(cv2.CAP_PROP_FPS)

                    self._webcam_cap = cap
                    self._camera_backend = "webcam"
                    self._init_camera_matrix(actual_w, actual_h)
                    logger.info(
                        "USB webcam initialized: %dx%d @ %.0f FPS",
                        actual_w, actual_h, actual_fps,
                    )
                    initialized = True
            except Exception as exc:
                logger.error("USB webcam init failed: %s", exc)

        else:
            logger.info(
                "Camera backend '%s' — no physical camera for ArUco landing",
                backend,
            )

        self._running = True
        self._thread = threading.Thread(target=self._run_detection, daemon=True)
        self._thread.start()
        return initialized

    def _init_camera_matrix(self, width: int, height: int) -> None:
        fx = fy = width * 0.8
        cx, cy = width / 2, height / 2
        self.camera_matrix = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float64)
        self.dist_coeffs = np.zeros(5, dtype=np.float64)

    def capture_frame(self) -> Optional[np.ndarray]:
        try:
            if self._camera_backend == "csi" and self._camera is not None:
                frame = self._camera.capture_array()
                return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            if self._camera_backend == "webcam" and self._webcam_cap is not None:
                ret, frame = self._webcam_cap.read()
                if ret:
                    return frame
                logger.warning("USB webcam read failed (transient)")
                return None

            return None
        except Exception as exc:
            logger.error("Frame capture failed: %s", exc)
            return None

    def _run_detection(self) -> None:
        logger.info("ArUco detection thread started")
        while self._running:
            frame = self.capture_frame()
            if frame is not None:
                self.detect(frame)
            else:
                # Limit loop rate if camera not available
                time.sleep(0.033)

    def detect(self, frame: np.ndarray) -> MarkerPose:
        if self.camera_matrix is None:
            self._init_camera_matrix(frame.shape[1], frame.shape[0])

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)

        pose = MarkerPose()

        if ids is None or len(ids) == 0:
            with self._lock:
                self._last_pose = pose
            return pose

        target_idx = None
        for i, mid in enumerate(ids.flatten()):
            if mid == config.ARUCO_MARKER_ID:
                target_idx = i
                break

        if target_idx is None:
            with self._lock:
                self._last_pose = pose
            return pose

        marker_corners = corners[target_idx]
        rvec, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
            marker_corners,
            config.ARUCO_MARKER_SIZE_M,
            self.camera_matrix,
            self.dist_coeffs,
        )

        tx, ty, tz = tvec[0][0]
        pose.detected = True
        pose.marker_id = config.ARUCO_MARKER_ID
        pose.dx = float(tx)
        pose.dy = float(ty)
        pose.distance = float(math.sqrt(tx**2 + ty**2 + tz**2))
        pose.angle_x = float(math.atan2(tx, tz))
        pose.angle_y = float(math.atan2(ty, tz))

        with self._lock:
            self._last_pose = pose
            if pose.detected:
                self._last_detected_pose = pose
        return pose

    @property
    def last_pose(self) -> MarkerPose:
        with self._lock:
            return self._last_pose

    @property
    def last_detected_pose(self) -> MarkerPose:
        with self._lock:
            return self._last_detected_pose

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

        # Release CSI camera (picamera2)
        if self._camera:
            try:
                self._camera.stop()
            except Exception as exc:
                logger.error("Error stopping CSI camera: %s", exc)
            self._camera = None

        # Release USB webcam (OpenCV VideoCapture)
        if self._webcam_cap:
            try:
                self._webcam_cap.release()
            except Exception as exc:
                logger.error("Error releasing USB webcam: %s", exc)
            self._webcam_cap = None

        self._camera_backend = "none"
        with self._lock:
            self._last_pose = MarkerPose()
            self._last_detected_pose = MarkerPose()
            logger.info("ArUco landing camera stopped")
