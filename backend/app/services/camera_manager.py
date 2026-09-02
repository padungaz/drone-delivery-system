import logging
from typing import Dict, Any, Optional
from app.services.qr_scanner_service import QRScannerService

logger = logging.getLogger(__name__)


class CameraManager:
    """Camera Device Manager — Independent Control Layer.
    
    Responsibilities:
    - Manage camera connection state (Start/Stop stream)
    - Provide manual test triggers for QR Code Scanning and ArUco Detection
    - Return camera status payload
    """

    _instance: Optional["CameraManager"] = None

    def __init__(self):
        self.qr_service = QRScannerService.get_instance()

    @classmethod
    def get_instance(cls) -> "CameraManager":
        if cls._instance is None:
            cls._instance = CameraManager()
        return cls._instance

    def update_config(self, simulator_mode: Optional[bool] = None, camera_index: Optional[int] = None) -> None:
        """Dynamically update camera simulator mode and camera index."""
        self.qr_service.update_config(simulator_mode=simulator_mode, camera_index=camera_index)
        logger.info("CameraManager updated config: simulator_mode=%s, camera_index=%s", simulator_mode, camera_index)

    def start_camera(self) -> bool:
        """Start physical/simulated Camera scanner thread."""
        logger.info("CameraManager: Starting Camera Service...")
        return self.qr_service.start_camera_scanner()

    def stop_camera(self) -> bool:
        """Stop physical/simulated Camera scanner thread."""
        logger.info("CameraManager: Stopping Camera Service...")
        return self.qr_service.stop_camera_scanner()

    def get_status(self) -> Dict[str, Any]:
        """Return current status of Camera device."""
        status = self.qr_service.get_status()
        status["device_name"] = "CAM01"
        status["type"] = "CAMERA"
        status["connected"] = status.get("is_active") or status.get("simulator_mode", False)
        status["status"] = "ONLINE" if (status.get("is_active") or status.get("simulator_mode")) else "OFFLINE"
        return status

    async def scan_qr_auto(
        self,
        expected_product_id: Optional[str] = None,
        timeout_sec: float = 8.0,
        is_verify: bool = False,
    ) -> Dict[str, Any]:
        """Auto QR Scan invocation for Station Service FSM."""
        return await self.qr_service.capture_and_scan_qr(
            timeout_sec=timeout_sec,
            expected_product_id=expected_product_id,
            is_verify=is_verify,
        )

    async def test_qr_scan(self, raw_qr: str = "TEST_PROD_999") -> Dict[str, Any]:
        """Manual test trigger for QR code scanning."""
        logger.info("CameraManager: Executing manual QR Scan test for content: %s", raw_qr)
        res = await self.qr_service.process_qr_code(raw_qr, source="MANUAL_TEST")
        return res

    async def scan_real_camera_snapshot(self) -> Dict[str, Any]:
        """Capture live frame from real physical USB camera and decode QR code."""
        return await self.qr_service.scan_real_camera_snapshot()

    def get_latest_frame_bytes(self) -> Optional[bytes]:
        return self.qr_service.get_latest_frame_bytes()

