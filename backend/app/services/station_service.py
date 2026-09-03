import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.models.schemas import (
    PLCCommand,
    RobotCommand,
    StationOperationResponse,
    StorageSlotStatus,
)
from app.services.plc_manager import PLCManager, slot_to_z_level, Z_LEVEL_LABELS, Z_LEVEL_HOME
from app.services.robot_manager import RobotManager
from app.services.camera_manager import CameraManager
from app.services.inventory_manager import InventoryManager
from app.websocket.manager import system_ws_manager
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class StationService:
    """Station Controller Service — Layer 3: Hardware Task Execution.

    Encapsulates internal hardware coordination for Docking Station:
    - Siemens S7-1200 PLC (DB15 protocol)
    - FAIRINO Robot Arm (Socket TCP driver)
    - USB Vision Camera CAM01 (OpenCV QRCodeDetector)
    - Inventory Storage Slots (A1..C3)

    Operations:
    - LOAD_PRODUCT   (Export / Delivery: Storage Slot -> Drone Dock)
    - UNLOAD_PRODUCT (Import / Pickup: Drone Dock -> Storage Slot)

    This service executes hardware sequences autonomously and reports high-level
    operation status without storing FSM step blobs in the database.
    """

    _instance: Optional["StationService"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(StationService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, session: Optional[AsyncSession] = None):
        if session is not None:
            self.session = session
        if not getattr(self, "_initialized", False):
            self.plc_mgr = PLCManager.get_instance()
            self.robot_mgr = RobotManager.get_instance()
            self.cam_mgr = CameraManager.get_instance()
            self.status: str = "IDLE"          # "IDLE", "RUNNING", "COMPLETED", "FAILED"
            self.current_operation: Optional[str] = None # "LOAD_PRODUCT", "UNLOAD_PRODUCT"
            self.current_action: str = "READY" # e.g. "PLC_LOCK_DRONE", "ROBOT_PICK_SLOT"
            self.target_slot: Optional[str] = None
            self.product_id: Optional[str] = None
            self.message: str = "Station is ready"
            self._initialized = True

    @classmethod
    def get_instance(cls) -> "StationService":
        if cls._instance is None:
            cls._instance = StationService()
        return cls._instance

    def get_status(self) -> StationOperationResponse:
        return StationOperationResponse(
            station_id="STATION_WH_001",
            operation=self.current_operation or "NONE",
            status=self.status,
            current_action=self.current_action,
            target_slot=self.target_slot,
            product_id=self.product_id,
            message=self.message,
        )

    async def _broadcast_status(self, action: str, msg: str, status: str = "RUNNING") -> None:
        self.current_action = action
        self.message = msg
        self.status = status
        logger.info("[StationService] %s: %s", action, msg)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                system_ws_manager.broadcast("STATION_STATUS", self.get_status().model_dump())
            )
        except RuntimeError:
            pass

    async def _plc_cmd(
        self,
        cmd: PLCCommand,
        success_attr: str,
        expected: bool,
        error_code: str,
        timeout: Optional[float] = None,
    ) -> None:
        """Unified PLC command helper: execute + verify result in one call.

        Eliminates the Double-Waiting anti-pattern where execute_command already
        waits for handshake but station_service called wait_for_status again.

        In simulator mode:  execute_command sets the state synchronously → the
                            attribute check passes immediately.
        In real HW mode:    execute_command performs the full handshake;
                            if the attribute is still not at expected value
                            (e.g. E-Stop fired), wait_for_status adds a follow-up poll.

        Args:
            cmd:          PLCCommand to execute.
            success_attr: PLCManager boolean attribute to check after execution.
            expected:     Expected boolean value of success_attr.
            error_code:   RuntimeError message if verification fails.
            timeout:      Real-HW follow-up wait limit in seconds (None = no timeout).

        Raises:
            RuntimeError: If the PLC state does not reach expected.
        """
        status = await self.plc_mgr.execute_command(cmd)
        # Fast-path: check result immediately (works for both sim and real after handshake)
        if getattr(status, success_attr, None) != expected:
            if not self.plc_mgr.simulator_mode:
                # Real HW: follow-up poll without timeout (waits until state reaches expected or E-Stop)
                await self.plc_mgr.wait_for_status(success_attr, expected, timeout_sec=timeout)
            else:
                raise RuntimeError(error_code)

    async def execute_load_product(self, target_slot: str, product_id: str, session: AsyncSession) -> bool:
        """LOAD_PRODUCT Operation (Drone Delivery / Export): Warehouse Slot -> Drone Dock.

        Optimized FSM Sequence:
          1. Drone Detect (drone_detected == TRUE, no timeout limit)
          2. Lock Drone (cmd_lock_drone -> plc_locked_state == TRUE)
          3. Robot Pick From Storage (PICK target_slot)
          4. QR Verify (Camera CAM01 verifies product QR code with 8s timeout; continues if error)
          5. Z Up (cmd_z_up -> plc_z_is_up == TRUE, PLC hardware interlock ensures Robot clearance)
          6. Robot Place Product onto Drone (PLACE N1)
          7. Z Down (cmd_z_down -> plc_z_is_down == TRUE)
          8. Unlock Drone (cmd_unlock_drone -> plc_locked_state == FALSE)
          9. Complete / Takeoff Ready
        """
        self.current_operation = "LOAD_PRODUCT"
        self.target_slot = target_slot
        self.product_id = product_id

        inv_mgr = InventoryManager(session)
        cam_mgr = CameraManager.get_instance()

        try:
            # 1. Drone Detect (No timeout - waits until Drone lands)
            await self._broadcast_status("1. DRONE_DETECT", "Checking Drone landing at Dock N1...")
            if not self.plc_mgr.drone_detected and self.plc_mgr.simulator_mode:
                self.plc_mgr.set_drone_detected(True)
            try:
                await self.plc_mgr.wait_for_status("drone_detected", True, timeout_sec=None)
            except Exception as e:
                raise RuntimeError(f"ERROR_DRONE_NOT_DETECTED: Lỗi phát hiện Drone tại Dock N1 ({e})")

            # 2. Lock Drone
            await self._broadcast_status("2. LOCK_DRONE", "PLC Locking drone clamps (DB15.DBX0.0)...")
            await self._plc_cmd(
                PLCCommand.LOCK_DRONE, "plc_locked_state", True,
                "ERROR_PLC_LOCK_FAILED: PLC không thể khóa ngàm kẹp cố định Drone",
            )

            # 3. PLC Z-Axis: Nâng trục Z đến tầng ô kho (A hoặc B)
            z_level = slot_to_z_level(target_slot)
            z_label = Z_LEVEL_LABELS.get(z_level, str(z_level))
            await self._broadcast_status("3. PLC_Z_TO_SLOT", f"PLC nâng trục Z đến tầng {z_label} (DB15.DBW8={z_level})...")
            if not await self.plc_mgr.move_z_to_level(z_level):
                raise RuntimeError(f"ERROR_PLC_Z_MOVE_FAILED: PLC không thể di chuyển trục Z đến tầng {z_label}")

            # 4. Robot Pick From Storage
            await self._broadcast_status("4. ROBOT_PICK_SLOT", f"Robot picking product from slot {target_slot}...")
            try:
                await self.robot_mgr.execute_command(RobotCommand.PICK, slot=target_slot)
            except Exception as e:
                raise RuntimeError(f"ERROR_ROBOT_PICK_FAILED: Robot gắp hàng từ ô {target_slot} thất bại ({e})")

            # 5. QR Verify (Giữ timeout quét QR 8s; sau 8s quét được hay không cũng tắt camera ngay)
            await self._broadcast_status("5. QR_VERIFY", f"Camera verifying QR code for product {product_id}...")
            await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                "status": "SCANNING",
                "product_id": f"Đang đối soát {product_id}...",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "message": f"📷 Trạm Drone: Đang đối soát mã QR kiện hàng {product_id}...",
            })
            try:
                scan_res = await cam_mgr.scan_qr_auto(expected_product_id=product_id, timeout_sec=8.0, is_verify=True)
                if scan_res.get("status") != "success":
                    err_msg = scan_res.get("message", f"Không thể xác thực mã QR cho sản phẩm {product_id}")
                    await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                        "status": "NOT_FOUND",
                        "product_id": product_id,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "message": f"⚠️ Trạm Drone: Cảnh báo đối soát QR không khớp ({err_msg}). Vẫn tiếp tục nạp hàng theo kế hoạch!",
                    })
                    logger.warning("⚠️ Trạm Drone: Đối soát QR không thành công (%s), tiếp tục bước tiếp theo.", err_msg)
                else:
                    scanned_code = scan_res.get("product_id") or product_id
                    await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                        "status": "DETECTED",
                        "product_id": scanned_code,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "message": f"✅ Trạm Drone: Đã đối soát khớp mã QR: {scanned_code}",
                    })
                    logger.info("✅ QR Code verified for product %s (%s)", product_id, scan_res.get("message"))
            finally:
                # Quét được hay không quét được sau 8s cũng tắt camera ngay lập tức
                try:
                    cam_mgr.stop_camera()
                    logger.info("📷 Trạm Drone: Đã tắt Camera ngay sau bước 5 đối soát QR.")
                except Exception as cam_err:
                    logger.warning("Error stopping camera after QR verify: %s", cam_err)

            # 6. PLC Z-Axis: Nâng trục Z đến tầng Drone N1
            z_dock = slot_to_z_level("N1")
            z_dock_label = Z_LEVEL_LABELS.get(z_dock, str(z_dock))
            await self._broadcast_status("6. PLC_Z_TO_DOCK", f"PLC nâng trục Z đến tầng {z_dock_label} (DB15.DBW8={z_dock})...")
            if not await self.plc_mgr.move_z_to_level(z_dock):
                raise RuntimeError(f"ERROR_PLC_Z_MOVE_FAILED: PLC không thể di chuyển trục Z đến tầng {z_dock_label} (>20s)")

            # 7. Robot Place Product onto Drone Dock N1
            await self._broadcast_status("7. ROBOT_PLACE_DOCK", "Robot placing product onto Drone Dock N1...")
            try:
                await self.robot_mgr.execute_command(RobotCommand.PLACE_PRODUCT, slot="N1")
            except Exception as e:
                raise RuntimeError(f"ERROR_ROBOT_PLACE_FAILED: Robot đặt hàng lên Drone N1 thất bại ({e})")

            # 8. PLC Z-Axis: Đưa trục Z về HOME an toàn
            await self._broadcast_status("8. PLC_Z_TO_HOME", "PLC đưa trục Z về vị trí HOME an toàn (DB15.DBW8=0)...")
            if not await self.plc_mgr.move_z_to_level(Z_LEVEL_HOME):
                raise RuntimeError("ERROR_PLC_Z_MOVE_FAILED: PLC không thể đưa trục Z về vị trí HOME an toàn (>20s)")

            # 9. Unlock Drone
            await self._broadcast_status("9. UNLOCK_DRONE", "PLC Unlocking drone clamps (DB15.DBX0.1)...")
            await self._plc_cmd(
                PLCCommand.UNLOCK_DRONE, "plc_locked_state", False,
                "ERROR_PLC_UNLOCK_FAILED: PLC mở ngàm kẹp Drone thất bại (>5s)",
            )

            # 10. Clear Storage Slot in Inventory & Finish
            await inv_mgr.update_slot(target_slot, StorageSlotStatus.EMPTY, product_id=None)
            await self._broadcast_status("10. TAKEOFF_COMPLETE", f"Đã nạp sản phẩm {product_id} lên Drone thành công. Sẵn sàng cất cánh!", status="COMPLETED")
            return True

        except Exception as err:
            logger.error("Station LOAD_PRODUCT failed: %s", err)
            await self._broadcast_status("LOAD_FAILED", f"LOAD_PRODUCT failed: {err}", status="FAILED")
            raise err
        finally:
            try:
                cam_mgr.stop_camera()
            except Exception as cam_err:
                logger.warning("Error stopping camera: %s", cam_err)

    async def execute_unload_product(self, target_slot: str, product_id: str, session: AsyncSession) -> bool:
        """UNLOAD_PRODUCT Operation (Drone Pickup / Import): Drone Dock N1 -> Warehouse Slot.

        Optimized FSM Sequence:
          1. Drone Detect (drone_detected == TRUE)
          2. Lock Drone (cmd_lock_drone -> plc_locked_state == TRUE)
          3. Z Up to Dock N1 (DB15.DBW8=3 -> DB15.DBX2.7 == TRUE)
          4. Robot Pick from Drone Dock (PICK N1)
          5. QR Scan (Camera CAM01 scans product QR code, timeout 8s, turn off camera immediately)
          6. Z to Target Slot (DB15.DBW8=1/2 -> DB15.DBX2.7 == TRUE)
          7. Store Product (STORE target_slot)
          8. Z Down to Home (DB15.DBW8=0 -> DB15.DBX2.7 == TRUE)
          9. Unlock Drone (cmd_unlock_drone -> plc_locked_state == FALSE)
          10. Complete / Takeoff Ready
        """
        self.current_operation = "UNLOAD_PRODUCT"
        self.target_slot = target_slot
        self.product_id = product_id

        inv_mgr = InventoryManager(session)
        cam_mgr = CameraManager.get_instance()

        try:
            # 1. Drone Detect (No timeout - waits until Drone lands)
            await self._broadcast_status("1. DRONE_DETECT", "Checking Drone landing at Dock N1...")
            if not self.plc_mgr.drone_detected and self.plc_mgr.simulator_mode:
                self.plc_mgr.set_drone_detected(True)
            try:
                await self.plc_mgr.wait_for_status("drone_detected", True, timeout_sec=None)
            except Exception as e:
                raise RuntimeError(f"ERROR_DRONE_NOT_DETECTED: Lỗi phát hiện Drone tại Dock N1 ({e})")

            # 2. Lock Drone
            await self._broadcast_status("2. LOCK_DRONE", "PLC Locking drone clamps (DB15.DBX0.0)...")
            await self._plc_cmd(
                PLCCommand.LOCK_DRONE, "plc_locked_state", True,
                "ERROR_PLC_LOCK_FAILED: PLC không thể khóa ngàm kẹp cố định Drone",
            )

            # 3. PLC Z-Axis: Nâng trục Z đến tầng Drone N1
            z_dock = slot_to_z_level("N1")
            z_dock_label = Z_LEVEL_LABELS.get(z_dock, str(z_dock))
            await self._broadcast_status("3. PLC_Z_TO_DOCK", f"PLC nâng trục Z đến tầng {z_dock_label} (DB15.DBW8={z_dock})...")
            if not await self.plc_mgr.move_z_to_level(z_dock):
                raise RuntimeError(f"ERROR_PLC_Z_MOVE_FAILED: PLC không thể di chuyển trục Z đến tầng {z_dock_label}")

            # 4. Robot Pick from Drone Dock N1
            await self._broadcast_status("4. ROBOT_PICK_DOCK", "Robot picking product from Drone Dock N1...")
            try:
                await self.robot_mgr.execute_command(RobotCommand.PICK_PRODUCT, slot="N1")
            except Exception as e:
                raise RuntimeError(f"ERROR_ROBOT_PICK_FAILED: Robot gắp hàng từ Drone N1 thất bại ({e})")

            # 5. QR Scan (Giữ timeout quét QR 8s; sau 8s quét được hay không cũng tắt camera ngay)
            await self._broadcast_status("5. QR_SCAN", f"Camera scanning QR code for product {product_id}...")
            await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                "status": "SCANNING",
                "product_id": "Đang quét...",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "message": f"📷 Trạm Drone: Đang quét mã QR kiện hàng...",
            })
            try:
                scan_res = await cam_mgr.scan_qr_auto(expected_product_id=product_id, timeout_sec=8.0, is_verify=False)
                if scan_res.get("status") != "success":
                    err_msg = scan_res.get("message", f"Không thể quét mã QR cho sản phẩm {product_id}")
                    await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                        "status": "NOT_FOUND",
                        "product_id": product_id,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "message": f"⚠️ Trạm Drone: Cảnh báo không nhận diện được mã QR ({err_msg}). Sử dụng mã mặc định và tiếp tục cất hàng.",
                    })
                    logger.warning("⚠️ Trạm Drone: Quét QR không thành công (%s), tiếp tục cất vào kho với mã %s.", err_msg, product_id)
                else:
                    if scan_res.get("product_id"):
                        product_id = scan_res["product_id"]
                        self.product_id = product_id
                    await system_ws_manager.broadcast("CAMERA_VISION_UPDATE", {
                        "status": "DETECTED",
                        "product_id": product_id,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "message": f"✅ Trạm Drone: Đã nhận diện mã QR: {product_id}",
                    })
                    logger.info("✅ QR Code scanned: assigned product ID %s", product_id)
            finally:
                # Quét được hay không quét được sau 8s cũng tắt camera ngay lập tức
                try:
                    cam_mgr.stop_camera()
                    logger.info("📷 Trạm Drone: Đã tắt Camera ngay sau bước 5 quét QR.")
                except Exception as cam_err:
                    logger.warning("Error stopping camera after QR scan: %s", cam_err)

            # 6. PLC Z-Axis: Nâng trục Z đến tầng ô kho (A hoặc B)
            z_slot = slot_to_z_level(target_slot)
            z_slot_label = Z_LEVEL_LABELS.get(z_slot, str(z_slot))
            await self._broadcast_status("6. PLC_Z_TO_SLOT", f"PLC di chuyển trục Z đến tầng {z_slot_label} (DB15.DBW8={z_slot})...")
            if not await self.plc_mgr.move_z_to_level(z_slot):
                raise RuntimeError(f"ERROR_PLC_Z_MOVE_FAILED: PLC không thể di chuyển trục Z đến tầng {z_slot_label}")

            # 7. Store Product into Storage Slot
            await self._broadcast_status("7. ROBOT_STORE_SLOT", f"Robot storing product into slot {target_slot}...")
            try:
                await self.robot_mgr.execute_command(RobotCommand.STORE, slot=target_slot)
            except Exception as e:
                raise RuntimeError(f"ERROR_ROBOT_STORE_FAILED: Robot cất hàng vào ô {target_slot} thất bại ({e})")

            # 8. PLC Z-Axis: Đưa trục Z về HOME an toàn
            await self._broadcast_status("8. PLC_Z_TO_HOME", "PLC đưa trục Z về vị trí HOME an toàn (DB15.DBW8=0)...")
            if not await self.plc_mgr.move_z_to_level(Z_LEVEL_HOME):
                raise RuntimeError("ERROR_PLC_Z_MOVE_FAILED: PLC không thể đưa trục Z về vị trí HOME an toàn")

            # 9. Unlock Drone
            await self._broadcast_status("9. UNLOCK_DRONE", "PLC Unlocking drone clamps (DB15.DBX0.1)...")
            await self._plc_cmd(
                PLCCommand.UNLOCK_DRONE, "plc_locked_state", False,
                "ERROR_PLC_UNLOCK_FAILED: PLC mở ngàm kẹp Drone thất bại",
            )

            # 10. Assign product to Storage Slot in Inventory & Finish
            await inv_mgr.update_slot(target_slot, StorageSlotStatus.OCCUPIED, product_id=product_id)
            await self._broadcast_status("10. TAKEOFF_COMPLETE", f"Đã cất sản phẩm {product_id} vào ô {target_slot} thành công. Drone sẵn sàng cất cánh!", status="COMPLETED")
            return True

        except Exception as err:
            logger.error("Station UNLOAD_PRODUCT failed: %s", err)
            await self._broadcast_status("UNLOAD_FAILED", f"UNLOAD_PRODUCT failed: {err}", status="FAILED")
            raise err
        finally:
            try:
                cam_mgr.stop_camera()
            except Exception as cam_err:
                logger.warning("Error stopping camera: %s", cam_err)


