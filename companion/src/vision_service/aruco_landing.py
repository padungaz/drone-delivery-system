import logging
import math
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
    """ArUco marker detection and LANDING_TARGET pose estimation."""

    def __init__(self):
        dict_id = ARUCO_DICT_MAP.get(config.ARUCO_DICTIONARY, cv2.aruco.DICT_4X4_50)
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        self.camera_matrix: Optional[np.ndarray] = None
        self.dist_coeffs: Optional[np.ndarray] = None
        self._camera = None
        self._last_pose = MarkerPose()

    def init_camera(self) -> bool:
        if not config.IS_PI or config.CAMERA_BACKEND != "csi":
            logger.info("Skipping Picamera2 init in simulation mode")
            return False

        try:
            from picamera2 import Picamera2

            self._camera = Picamera2()
            config_cam = self._camera.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"}
            )
            self._camera.configure(config_cam)
            self._camera.start()
            logger.info("CSI camera initialized")
            self._init_camera_matrix(640, 480)
            return True
        except ImportError:
            logger.warning("picamera2 not available — using mock camera for dev")
            return False
        except Exception as exc:
            logger.error("Camera init failed: %s", exc)
            return False

    def _init_camera_matrix(self, width: int, height: int) -> None:
        fx = fy = width * 0.8
        cx, cy = width / 2, height / 2
        self.camera_matrix = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float64)
        self.dist_coeffs = np.zeros(5, dtype=np.float64)

    def capture_frame(self) -> Optional[np.ndarray]:
        if self._camera is None:
            return None
        try:
            frame = self._camera.capture_array()
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception as exc:
            logger.error("Frame capture failed: %s", exc)
            return None

    def detect(self, frame: np.ndarray) -> MarkerPose:
        if self.camera_matrix is None:
            self._init_camera_matrix(frame.shape[1], frame.shape[0])

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)

        pose = MarkerPose()

        if ids is None or len(ids) == 0:
            self._last_pose = pose
            return pose

        target_idx = None
        for i, mid in enumerate(ids.flatten()):
            if mid == config.ARUCO_MARKER_ID:
                target_idx = i
                break

        if target_idx is None:
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

        self._last_pose = pose
        return pose

    @property
    def last_pose(self) -> MarkerPose:
        return self._last_pose

    def stop(self) -> None:
        if self._camera:
            self._camera.stop()
            self._camera = None
            logger.info("Camera stopped")
