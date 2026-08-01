import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional

# Attempt to import OpenCV safely
try:
    import cv2
    OPENCV_AVAILABLE = True
except (ImportError, Exception) as cv2_err:
    OPENCV_AVAILABLE = False
    cv2 = None
    logger = logging.getLogger(__name__)
    logger.warning("OpenCV python package (cv2) not available. Camera scanning mode will fallback to simulated API mode.")

logger = logging.getLogger(__name__)

from app.database.repository import async_session
from app.models.schemas import StorageSlotStatus
from app.services.inventory_manager import InventoryManager
from app.storage.repository import StorageRepository
from app.websocket.manager import system_ws_manager
from app.websocket.handler import manager as drone_ws_manager

DEFAULT_CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "1"))
SCAN_DEBOUNCE_SEC = float(os.getenv("SCAN_DEBOUNCE_SEC", "5.0"))


class QRScannerService:
    """Integrated Backend Service for Camera QR Code Scanning & Automatic Warehouse Inventory Sorting.
    
    Responsibilities:
    1. Supports reading USB Camera frames via OpenCV QRCodeDetector (if camera is connected).
    2. Parses scanned QR code payloads (plain text product IDs or JSON objects).
    3. Finds the first available storage slot in warehouse (A1..C3 / Slot 1..9).
    4. Automatically updates slot status (OCCUPIED, product_id, qr_code, sender_name, sender_address).
    5. Broadcasts realtime inventory updates via WebSockets (`INVENTORY_STATUS` & `storage_update`).
    6. Provides HTTP control endpoints (/api/inventory/scan-qr, /api/inventory/camera-scan/*).
    """

    _instance: Optional["QRScannerService"] = None

    def __init__(self, camera_index: int = DEFAULT_CAMERA_INDEX):
        self.camera_index = camera_index
        self.is_active = False
        self.camera_thread: Optional[threading.Thread] = None
        self.cap = None
        self.detector = cv2.QRCodeDetector() if (OPENCV_AVAILABLE and cv2 is not None) else None
        
        # Debounce cache: {qr_text: timestamp}
        self._sent_cache: Dict[str, float] = {}
        
        # Scanner metrics
        self.last_scanned_qr: Optional[str] = None
        self.last_assigned_slot: Optional[str] = None
        self.last_scan_time: Optional[str] = None
        self.total_scans_count: int = 0

    @classmethod
    def get_instance(cls) -> "QRScannerService":
        if cls._instance is None:
            cam_idx = int(os.getenv("CAMERA_INDEX", "1"))
            cls._instance = QRScannerService(camera_index=cam_idx)
        return cls._instance

    def _is_debounced(self, qr_text: str) -> bool:
        """Check if QR code was scanned recently (within debounce window)."""
        now = time.time()
        last_time = self._sent_cache.get(qr_text)
        if last_time is not None and (now - last_time) < SCAN_DEBOUNCE_SEC:
            return True
        return False

    def _mark_scanned(self, qr_text: str) -> None:
        """Mark QR code as scanned and purge expired cache items."""
        now = time.time()
        self._sent_cache[qr_text] = now
        expired = [k for k, ts in self._sent_cache.items() if now - ts > SCAN_DEBOUNCE_SEC * 2]
        for k in expired:
            del self._sent_cache[k]

    async def process_qr_code(self, raw_qr: str, source: str = "CAMERA") -> Dict[str, Any]:
        """Core Warehouse Inventory Sorting Algorithm.
        
        Parses raw QR string, extracts product metadata, assigns item to the first empty slot (A1..C3),
        saves to database, and broadcasts WebSocket state updates.
        """
        raw_qr = raw_qr.strip()
        if not raw_qr:
            return {"status": "error", "message": "Nội dung mã QR rỗng"}

        # Extract product_id, sender_name, address from raw QR
        product_id = raw_qr
        sender_name = "Khách hàng"
        address = "Kho trung tâm"

        # Check if raw_qr is a JSON payload
        if raw_qr.startswith("{") and raw_qr.endswith("}"):
            try:
                data = json.loads(raw_qr)
                if isinstance(data, dict):
                    product_id = str(
                        data.get("productId")
                        or data.get("product_id")
                        or data.get("qr")
                        or data.get("id")
                        or raw_qr
                    )
                    sender_name = str(data.get("senderName") or data.get("sender_name") or "Khách hàng")
                    address = str(data.get("address") or data.get("sender_address") or "Kho trung tâm")
            except Exception:
                pass

        async with async_session() as session:
            inv_mgr = InventoryManager(session)
            await inv_mgr.init_default_slots()

            # Check if product is already in a slot
            existing_slot = await inv_mgr.find_slot_by_product_id(product_id)
            if existing_slot:
                logger.info("Product %s already stored in slot %s", product_id, existing_slot.slot_name)
                return {
                    "status": "already_assigned",
                    "message": f"Sản phẩm [{product_id}] đã sẵn có ở Ô kho {existing_slot.slot_name}",
                    "slot_name": existing_slot.slot_name,
                    "slot_id": existing_slot.id,
                    "product_id": product_id,
                }

            # Find available empty slot
            free_slot = await inv_mgr.find_available_slot()
            if not free_slot:
                logger.error("Warehouse full! Cannot assign scanned product %s", product_id)
                return {
                    "status": "full",
                    "message": "Kho hàng đã đầy (9/9 ô đã có hàng)! Không thể lưu thêm.",
                }

            # Update DB Slot Record (both Smart Intralogistics and Legacy columns)
            now = datetime.utcnow()
            free_slot.status = StorageSlotStatus.OCCUPIED.value
            free_slot.product_id = product_id
            free_slot.qr_code = raw_qr
            free_slot.updated_time = now

            free_slot.is_empty = False
            free_slot.sender_name = sender_name
            free_slot.sender_address = address
            free_slot.item_created_at = now

            await session.commit()
            await session.refresh(free_slot)

            # Update metrics
            self.last_scanned_qr = product_id
            self.last_assigned_slot = free_slot.slot_name
            self.last_scan_time = now.isoformat()
            self.total_scans_count += 1

            # Broadcast Realtime WebSocket Events
            # 1. Broadcast to System WS (/ws/system)
            await system_ws_manager.broadcast("INVENTORY_STATUS", {
                "slot_name": free_slot.slot_name,
                "status": free_slot.status,
                "product_id": free_slot.product_id,
                "qr_code": free_slot.qr_code,
                "sender_name": free_slot.sender_name,
                "sender_address": free_slot.sender_address,
            })

            # 2. Broadcast to Drone/Client WS (/ws/client)
            storage_repo = StorageRepository(session)
            all_slots = await storage_repo.get_all_slots()
            state_resp = storage_repo.build_storage_state(all_slots)
            await drone_ws_manager.broadcast_to_clients({
                "type": "storage_update",
                "payload": state_resp.model_dump(mode="json", by_alias=True),
            })

            logger.info(
                "✅ [Backend QR Scanner] Auto-sorted Product %s -> Slot %s (ID #%d, Source: %s)",
                product_id,
                free_slot.slot_name,
                free_slot.id,
                source,
            )

            return {
                "status": "success",
                "message": f"Tự động quét QR mã [{product_id}] & Xếp vào Ô kho {free_slot.slot_name} thành công!",
                "slot_name": free_slot.slot_name,
                "slot_id": free_slot.id,
                "product_id": product_id,
                "sender_name": sender_name,
            }

    def _open_camera_device(self):
        """Attempt to open physical USB camera at camera_index, with fallback index search & CAP_DSHOW on Windows."""
        if cv2 is None:
            return None

        indices_to_try = [self.camera_index]
        for idx in range(3):
            if idx not in indices_to_try:
                indices_to_try.append(idx)

        for idx in indices_to_try:
            # On Windows, DirectShow backend (CAP_DSHOW) initializes USB Cameras much faster
            try:
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(idx)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        logger.info("✅ Physical USB Camera successfully opened at index %d", idx)
                        self.camera_index = idx
                        return cap
                    cap.release()
            except Exception:
                pass

            try:
                cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        logger.info("✅ Physical USB Camera successfully opened at index %d", idx)
                        self.camera_index = idx
                        return cap
                    cap.release()
            except Exception:
                pass

        return None

    def _draw_detection(self, frame, points, status_text: str, qr_str: Optional[str] = None):
        """Draw bounding box around QR code and overlay status text on frame."""
        if cv2 is None or frame is None:
            return frame

        # Draw QR bounding polygon box
        if points is not None and len(points) > 0:
            try:
                import numpy as np
                pts = points[0].astype(np.int32)
                cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 0), thickness=3)
            except Exception:
                pass

        # Overlay status banner
        overlay_color = (0, 255, 0) if "OK" in status_text else (0, 165, 255)
        cv2.putText(frame, f"USB Camera QR: {status_text}", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, overlay_color, 2)

        if qr_str:
            cv2.putText(frame, f"Data: {qr_str}", (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            if self.last_assigned_slot:
                cv2.putText(frame, f"Slot: {self.last_assigned_slot}", (15, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        return frame

    def _camera_loop(self) -> None:
        """Background thread loop: Captures USB Camera frames, draws overlay, opens desktop window & decodes QR codes."""
        if not OPENCV_AVAILABLE or cv2 is None:
            logger.warning("OpenCV not available. Stopping camera scanner loop.")
            self.is_active = False
            self.simulator_mode = True
            return

        logger.info("Starting Backend Camera QR Scanner loop (Attempting USB Camera index=%d)...", self.camera_index)
        self.cap = self._open_camera_device()

        if self.cap is None or not self.cap.isOpened():
            logger.warning("⚠️ No physical USB camera detected on indices 0..2. Falling back to Simulator Mode.")
            self.simulator_mode = True
            self.is_active = True
            return

        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        except Exception as set_err:
            logger.warning("Could not set camera frame resolution: %s", set_err)
        self.is_active = True
        self.simulator_mode = False
        self.show_preview = True
        self.latest_jpeg_bytes: Optional[bytes] = None

        window_name = "USB Camera QR Scanner - Smart Warehouse"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.is_active and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret or frame is None:
                time.sleep(0.05)
                continue

            status_text = "Scanning..."
            qr_str = None
            points = None

            try:
                data, points, _ = self.detector.detectAndDecode(frame)
                if data and data.strip():
                    qr_str = data.strip()
                    if self._is_debounced(qr_str):
                        status_text = f"Already Scanned [{qr_str}]"
                    else:
                        status_text = f"OK -> {qr_str}"
                        self._mark_scanned(qr_str)
                        logger.info("📷 USB Camera detected QR code: %s", qr_str)
                        loop.run_until_complete(self.process_qr_code(qr_str, source="USB_CAMERA"))
            except Exception as exc:
                logger.error("Error in camera frame QR detection: %s", exc)

            # Draw visual bounding box and status overlay
            self._draw_detection(frame, points, status_text, qr_str)

            # 1. Encode frame to JPEG for Web UI Stream
            try:
                _, jpeg_buf = cv2.imencode('.jpg', frame)
                if jpeg_buf is not None:
                    self.latest_jpeg_bytes = jpeg_buf.tobytes()
            except Exception:
                pass

            # 2. Display desktop window via cv2.imshow
            if self.show_preview:
                try:
                    cv2.imshow(window_name, frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        self.is_active = False
                        break
                except Exception:
                    pass

            time.sleep(0.04)  # ~25 FPS

        if self.cap is not None:
            self.cap.release()
            self.cap = None

        if cv2 is not None:
            try:
                cv2.destroyWindow(window_name)
            except Exception:
                pass

        loop.close()
        self.is_active = False
        logger.info("Backend Camera QR Scanner loop stopped.")

    def get_latest_frame_bytes(self) -> Optional[bytes]:
        """Return latest JPEG encoded frame bytes for web streaming."""
        return getattr(self, "latest_jpeg_bytes", None)

    async def notify_status_ws(self) -> None:
        """Broadcast camera active state to System WS & Drone WS clients."""
        status = self.get_status()
        await system_ws_manager.broadcast("CAMERA_STATUS", status)
        await drone_ws_manager.broadcast_to_clients({"type": "camera_status", "payload": status})

    def start_camera_scanner(self) -> bool:
        """Start the background camera QR scanning thread."""
        if self.is_active:
            logger.info("Backend Camera QR Scanner is already running.")
            return True

        global OPENCV_AVAILABLE, cv2
        if not OPENCV_AVAILABLE:
            try:
                import cv2
                OPENCV_AVAILABLE = True
                self.detector = cv2.QRCodeDetector()
            except Exception:
                OPENCV_AVAILABLE = False

        if not OPENCV_AVAILABLE:
            logger.warning("OpenCV not installed. Falling back to Camera Scanner Simulator Mode.")
            self.simulator_mode = True
            self.is_active = True
            return True

        self.is_active = True
        self.simulator_mode = False
        self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self.camera_thread.start()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.notify_status_ws())
        except RuntimeError:
            pass

        return True

    def stop_camera_scanner(self) -> bool:
        """Stop the background camera QR scanning thread."""
        self.is_active = False
        self.simulator_mode = False
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        logger.info("Stop command sent to Backend Camera QR Scanner.")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.notify_status_ws())
        except RuntimeError:
            pass

        return True

    def get_status(self) -> Dict[str, Any]:
        """Get current status and metrics of the backend QR scanner service."""
        global OPENCV_AVAILABLE
        return {
            "is_active": self.is_active,
            "simulator_mode": getattr(self, "simulator_mode", not OPENCV_AVAILABLE),
            "opencv_available": OPENCV_AVAILABLE,
            "camera_index": self.camera_index,
            "last_scanned_qr": self.last_scanned_qr,
            "last_assigned_slot": self.last_assigned_slot,
            "last_scan_time": self.last_scan_time,
            "total_scans_count": self.total_scans_count,
        }
