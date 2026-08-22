import asyncio
import logging
from typing import Optional

from app.models.schemas import (
    PLCCommand,
    RobotCommand,
    StationOperationResponse,
    StorageSlotStatus,
)
from app.services.plc_manager import PLCManager
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
        timeout: float = 5.0,
    ) -> None:
        """Unified PLC command helper: execute + verify result in one call.

        Eliminates the Double-Waiting anti-pattern where execute_command already
        waits for handshake but station_service called wait_for_status again.

        In simulator mode:  execute_command sets the state synchronously → the
                            attribute check passes immediately.
        In real HW mode:    execute_command performs the full handshake (≤25s);
                            if the attribute is still not at expected value
                            (e.g. E-Stop fired), wait_for_status adds a short
                            follow-up poll (timeout param, default 5s).

        Args:
            cmd:          PLCCommand to execute.
            success_attr: PLCManager boolean attribute to check after execution.
            expected:     Expected boolean value of success_attr.
            error_code:   RuntimeError message if verification fails.
            timeout:      Real-HW follow-up wait limit in seconds (default 5s).

        Raises:
            RuntimeError: If the PLC state does not reach expected within timeout.
        """
        status = await self.plc_mgr.execute_command(cmd)
        # Fast-path: check result immediately (works for both sim and real after handshake)
        if getattr(status, success_attr, None) != expected:
            if not self.plc_mgr.simulator_mode:
                # Real HW: short follow-up poll in case status was sampled mid-transition
                await self.plc_mgr.wait_for_status(success_attr, expected, timeout_sec=timeout)
            else:
                raise RuntimeError(error_code)

    async def execute_load_product(self, target_slot: str, product_id: str, session: AsyncSession) -> bool:
        """LOAD_PRODUCT Operation (Drone Delivery / Export): Warehouse Slot -> Drone Dock.

        Optimized FSM Sequence:
          1. Drone Detect (drone_detected == TRUE)
          2. Lock Drone (cmd_lock_drone -> plc_locked_state == TRUE)
          3. Robot Pick From Storage (PICK target_slot)
          4. QR Verify (Camera CAM01 verifies product QR code before Z Lift)
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
            # 1. Drone Detect
            await self._broadcast_status("1. DRONE_DETECT", "Checking Drone landing at Dock N1...")
            if not self.plc_mgr.drone_detected and self.plc_mgr.simulator_mode:
                self.plc_mgr.set_drone_detected(True)
            try:
                await self.plc_mgr.wait_for_status("drone_detected", True, timeout_sec=15.0)
            except Exception:
                raise RuntimeError("ERROR_DRONE_NOT_DETECTED: Quá thời gian chờ Drone hạ cánh tại bãi đáp Dock N1 (>15s)")

            # 2. Lock Drone
            await self._broadcast_status("2. LOCK_DRONE", "PLC Locking drone clamps (DB15.DBX0.0)...")
            await self._plc_cmd(
                PLCCommand.LOCK_DRONE, "plc_locked_state", True,
                "ERROR_PLC_LOCK_FAILED: PLC không thể khóa ngàm kẹp cố định Drone (>5s)",
            )

            # 3. Robot Pick From Storage
            await self._broadcast_status("3. ROBOT_PICK_SLOT", f"Robot picking product from slot {target_slot}...")
            try:
                await self.robot_mgr.execute_command(RobotCommand.PICK, slot=target_slot)
            except Exception as e:
                raise RuntimeError(f"ERROR_ROBOT_PICK_FAILED: Robot gắp hàng từ ô {target_slot} thất bại ({e})")

            # 4. QR Verify (Đối soát mã QR ngay tại vị trí dưới trước khi nâng Z)
            await self._broadcast_status("4. QR_VERIFY", f"Camera verifying QR code for product {product_id}...")
            scan_res = await cam_mgr.scan_qr_auto(expected_product_id=product_id, timeout_sec=8.0, is_verify=True)
            if scan_res.get("status") != "success":
                err_msg = scan_res.get("message", f"Không thể xác thực mã QR cho sản phẩm {product_id}")
                raise RuntimeError(f"ERROR_QR_VERIFY_FAILED: {err_msg}")
            logger.info("✅ QR Code verified for product %s (%s)", product_id, scan_res.get("message"))

            # 5. Z Up (PLC tự động interlock với Robot)
            await self._broadcast_status("5. PLC_Z_UP", "PLC Raising Z-axis lift to UP position (DB15.DBX0.2)...")
            await self._plc_cmd(
                PLCCommand.Z_UP, "plc_z_is_up", True,
                "ERROR_PLC_Z_UP_FAILED: PLC nâng trục Z thất bại hoặc quá thời gian (>5s)",
            )

            # 6. Robot Place Product onto Drone Dock N1
            await self._broadcast_status("6. ROBOT_PLACE_DOCK", "Robot placing product onto Drone Dock N1...")
            try:
                await self.robot_mgr.execute_command(RobotCommand.PLACE_PRODUCT, slot="N1")
            except Exception as e:
                raise RuntimeError(f"ERROR_ROBOT_PLACE_FAILED: Robot đặt hàng lên Drone N1 thất bại ({e})")

            # 7. Z Down
            await self._broadcast_status("7. PLC_Z_DOWN", "PLC Lowering Z-axis lift to DOWN position (DB15.DBX0.3)...")
            await self._plc_cmd(
                PLCCommand.Z_DOWN, "plc_z_is_down", True,
                "ERROR_PLC_Z_DOWN_FAILED: PLC hạ trục Z thất bại hoặc quá thời gian (>5s)",
            )

            # 8. Unlock Drone
            await self._broadcast_status("8. UNLOCK_DRONE", "PLC Unlocking drone clamps (DB15.DBX0.1)...")
            await self._plc_cmd(
                PLCCommand.UNLOCK_DRONE, "plc_locked_state", False,
                "ERROR_PLC_UNLOCK_FAILED: PLC mở ngàm kẹp Drone thất bại (>5s)",
            )

            # 9. Clear Storage Slot in Inventory & Finish
            await inv_mgr.update_slot(target_slot, StorageSlotStatus.EMPTY, product_id=None)
            await self._broadcast_status("9. TAKEOFF_COMPLETE", f"Đã nạp sản phẩm {product_id} lên Drone thành công. Sẵn sàng cất cánh!", status="COMPLETED")
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
          3. Z Up (cmd_z_up -> plc_z_is_up == TRUE, PLC hardware interlock ensures Robot clearance)
          4. Robot Pick from Drone Dock (PICK N1)
          5. Z Down (cmd_z_down -> plc_z_is_down == TRUE)
          6. QR Scan (Camera CAM01 scans product QR code)
          7. Store Product (STORE target_slot)
          8. Unlock Drone (cmd_unlock_drone -> plc_locked_state == FALSE)
          9. Complete / Takeoff Ready
        """
        self.current_operation = "UNLOAD_PRODUCT"
        self.target_slot = target_slot
        self.product_id = product_id

        inv_mgr = InventoryManager(session)
        cam_mgr = CameraManager.get_instance()

        try:
            # 1. Drone Detect
            await self._broadcast_status("1. DRONE_DETECT", "Checking Drone landing at Dock N1...")
            if not self.plc_mgr.drone_detected and self.plc_mgr.simulator_mode:
                self.plc_mgr.set_drone_detected(True)
            try:
                await self.plc_mgr.wait_for_status("drone_detected", True, timeout_sec=15.0)
            except Exception:
                raise RuntimeError("ERROR_DRONE_NOT_DETECTED: Quá thời gian chờ Drone hạ cánh tại bãi đáp Dock N1 (>15s)")

            # 2. Lock Drone
            await self._broadcast_status("2. LOCK_DRONE", "PLC Locking drone clamps (DB15.DBX0.0)...")
            await self._plc_cmd(
                PLCCommand.LOCK_DRONE, "plc_locked_state", True,
                "ERROR_PLC_LOCK_FAILED: PLC không thể khóa ngàm kẹp cố định Drone (>5s)",
            )

            # 3. Z Up (PLC tự động interlock với Robot)
            await self._broadcast_status("3. PLC_Z_UP", "PLC Raising Z-axis lift to UP position (DB15.DBX0.2)...")
            await self._plc_cmd(
                PLCCommand.Z_UP, "plc_z_is_up", True,
                "ERROR_PLC_Z_UP_FAILED: PLC nâng trục Z thất bại hoặc quá thời gian (>5s)",
            )

            # 4. Robot Pick from Drone Dock N1
            await self._broadcast_status("4. ROBOT_PICK_DOCK", "Robot picking product from Drone Dock N1...")
            try:
                await self.robot_mgr.execute_command(RobotCommand.PICK_PRODUCT, slot="N1")
            except Exception as e:
                raise RuntimeError(f"ERROR_ROBOT_PICK_FAILED: Robot gắp hàng từ Drone N1 thất bại ({e})")

            # 5. Z Down
            await self._broadcast_status("5. PLC_Z_DOWN", "PLC Lowering Z-axis lift to DOWN position (DB15.DBX0.3)...")
            await self._plc_cmd(
                PLCCommand.Z_DOWN, "plc_z_is_down", True,
                "ERROR_PLC_Z_DOWN_FAILED: PLC hạ trục Z thất bại hoặc quá thời gian (>5s)",
            )

            # 6. QR Scan
            await self._broadcast_status("6. QR_SCAN", f"Camera scanning QR code for product {product_id}...")
            scan_res = await cam_mgr.scan_qr_auto(expected_product_id=product_id, timeout_sec=8.0, is_verify=False)
            if scan_res.get("status") != "success":
                err_msg = scan_res.get("message", f"Không thể quét mã QR cho sản phẩm {product_id}")
                raise RuntimeError(f"ERROR_QR_SCAN_FAILED: {err_msg}")
            if scan_res.get("product_id"):
                product_id = scan_res["product_id"]
                self.product_id = product_id
                logger.info("✅ QR Code scanned: assigned product ID %s", product_id)

            # 7. Store Product into Storage Slot
            await self._broadcast_status("7. ROBOT_STORE_SLOT", f"Robot storing product into slot {target_slot}...")
            try:
                await self.robot_mgr.execute_command(RobotCommand.STORE, slot=target_slot)
            except Exception as e:
                raise RuntimeError(f"ERROR_ROBOT_STORE_FAILED: Robot cất hàng vào ô {target_slot} thất bại ({e})")

            # 8. Unlock Drone
            await self._broadcast_status("8. UNLOCK_DRONE", "PLC Unlocking drone clamps (DB15.DBX0.1)...")
            await self._plc_cmd(
                PLCCommand.UNLOCK_DRONE, "plc_locked_state", False,
                "ERROR_PLC_UNLOCK_FAILED: PLC mở ngàm kẹp Drone thất bại (>5s)",
            )

            # 9. Assign product to Storage Slot in Inventory & Finish
            await inv_mgr.update_slot(target_slot, StorageSlotStatus.OCCUPIED, product_id=product_id)
            await self._broadcast_status("9. TAKEOFF_COMPLETE", f"Đã cất sản phẩm {product_id} vào ô {target_slot} thành công. Drone sẵn sàng cất cánh!", status="COMPLETED")
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


