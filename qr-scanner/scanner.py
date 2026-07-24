"""
QR Code Scanner — Camera capture + QR detection + debounce.

Sử dụng OpenCV built-in QRCodeDetector.
Fallback sang pyzbar nếu cần độ chính xác cao hơn.
"""

import json
import logging
import time
from typing import Callable, Optional

import cv2

import config

logger = logging.getLogger(__name__)


class QRCodeScanner:
    """Mở camera USB, liên tục quét QR code từ video frame."""

    def __init__(self, on_qr_detected: Optional[Callable[[dict], None]] = None):
        """
        Args:
            on_qr_detected: Callback được gọi khi phát hiện QR mới (đã debounce).
                            Nhận dict chứa dữ liệu QR đã parse.
        """
        self.on_qr_detected = on_qr_detected
        self.cap: Optional[cv2.VideoCapture] = None
        self.detector = cv2.QRCodeDetector()
        self.running = False

        # Debounce: lưu {qr_content_hash: last_sent_timestamp}
        self._sent_cache: dict[str, float] = {}

    def open_camera(self) -> bool:
        """Mở camera USB."""
        logger.info(
            "Opening camera index=%d (%dx%d @ %dfps)",
            config.CAMERA_INDEX,
            config.CAMERA_WIDTH,
            config.CAMERA_HEIGHT,
            config.CAMERA_FPS,
        )
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)

        if not self.cap.isOpened():
            logger.error("Cannot open camera index %d", config.CAMERA_INDEX)
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)

        logger.info("Camera opened successfully")
        return True

    def close_camera(self) -> None:
        """Đóng camera."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            logger.info("Camera closed")

    def _cleanup_cache(self) -> None:
        """Xóa các entry debounce đã hết hạn."""
        now = time.time()
        expired = [
            key
            for key, ts in self._sent_cache.items()
            if now - ts > config.SCAN_CACHE_TTL_SEC
        ]
        for key in expired:
            del self._sent_cache[key]

    def _is_debounced(self, qr_content: str) -> bool:
        """Kiểm tra QR code đã được gửi gần đây chưa (debounce)."""
        now = time.time()
        last_sent = self._sent_cache.get(qr_content)
        if last_sent is not None and (now - last_sent) < config.SCAN_DEBOUNCE_SEC:
            return True
        return False

    def _mark_sent(self, qr_content: str) -> None:
        """Đánh dấu QR code đã được gửi."""
        self._sent_cache[qr_content] = time.time()

    def _parse_qr_data(self, raw_text: str) -> Optional[dict]:
        """Parse QR content thành dict. Chỉ chấp nhận JSON hợp lệ."""
        try:
            data = json.loads(raw_text)
            # Validate required fields
            if "senderName" not in data or "address" not in data:
                logger.warning("QR missing required fields: %s", raw_text)
                return None
            return data
        except (json.JSONDecodeError, TypeError):
            logger.warning("QR is not valid JSON: %s", raw_text[:100])
            return None

    def _draw_detection(
        self, frame, points, qr_data: Optional[dict], status: str
    ) -> None:
        """Vẽ khung quanh QR code và trạng thái lên frame."""
        if points is not None and len(points) > 0:
            pts = points[0].astype(int)
            n = len(pts)
            for i in range(n):
                cv2.line(
                    frame,
                    tuple(pts[i]),
                    tuple(pts[(i + 1) % n]),
                    (0, 255, 0),
                    3,
                )

        # Status text
        color = (0, 255, 0) if status == "OK" else (0, 165, 255)
        cv2.putText(
            frame,
            f"QR: {status}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2,
        )

        if qr_data:
            sender = qr_data.get("senderName", "?")
            address = qr_data.get("address", "?")
            cv2.putText(
                frame,
                f"Sender: {sender}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
            )
            cv2.putText(
                frame,
                f"Address: {address}",
                (10, 85),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
            )

    def run(self) -> None:
        """Main loop: đọc frame → detect QR → callback → hiển thị preview."""
        if self.cap is None or not self.cap.isOpened():
            if not self.open_camera():
                return

        self.running = True
        logger.info("Scanner started. Press 'q' to quit.")

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                logger.warning("Failed to read frame from camera")
                time.sleep(0.1)
                continue

            # Detect QR code
            data, points, _ = self.detector.detectAndDecode(frame)

            status = "Scanning..."
            qr_data = None

            if data:
                # QR detected
                qr_data = self._parse_qr_data(data)

                if qr_data is None:
                    status = "Invalid QR"
                elif self._is_debounced(data):
                    status = "Already scanned"
                else:
                    # New valid QR → fire callback
                    status = "OK"
                    self._mark_sent(data)
                    logger.info(
                        "QR detected: sender=%s, address=%s",
                        qr_data.get("senderName"),
                        qr_data.get("address"),
                    )
                    if self.on_qr_detected:
                        try:
                            self.on_qr_detected(qr_data)
                        except Exception as exc:
                            logger.error("Callback error: %s", exc)

            # Draw preview
            if config.SHOW_PREVIEW:
                self._draw_detection(frame, points, qr_data, status)
                cv2.imshow("QR Scanner - Warehouse", frame)

                # 'q' to quit
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("Quit requested by user")
                    self.running = False
                    break

            # Cleanup debounce cache periodically
            self._cleanup_cache()

        self.close_camera()
        if config.SHOW_PREVIEW:
            cv2.destroyAllWindows()

    def stop(self) -> None:
        """Dừng scanner loop."""
        self.running = False
