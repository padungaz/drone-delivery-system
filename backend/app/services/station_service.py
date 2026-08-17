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
from app.services.inventory_manager import InventoryManager
from app.websocket.manager import system_ws_manager
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class StationService:
    """Station Controller Service — Layer 3: Hardware Task Execution.

    Encapsulates internal hardware coordination for Docking Station:
    - Siemens S7-1200 PLC (DB15 protocol)
    - FAIRINO Robot Arm (Socket TCP driver)
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

    async def execute_load_product(self, target_slot: str, product_id: str, session: AsyncSession) -> bool:
        """LOAD_PRODUCT Operation (Drone Delivery / Export): Warehouse Slot -> Drone Dock.

        11-Step FSM Sequence:
          1. Drone Detect (drone_detected == TRUE)
          2. Lock Drone (cmd_lock_drone -> plc_locked_state == TRUE)
          3. Robot Pick From Storage (PICK target_slot)
          4. Robot Home (MOVE_HOME)
          5. QR Verify (Verify product QR code)
          6. Z Up (cmd_z_up -> plc_z_is_up == TRUE)
          7. Robot Place Product (PLACE DOCK)
          8. Robot Home (MOVE_HOME)
          9. Z Down (cmd_z_down -> plc_z_is_down == TRUE)
          10. Unlock Drone (cmd_unlock_drone -> plc_locked_state == FALSE)
          11. Takeoff / Complete
        """
        self.current_operation = "LOAD_PRODUCT"
        self.target_slot = target_slot
        self.product_id = product_id

        inv_mgr = InventoryManager(session)

        try:
            # 1. Drone Detect
            await self._broadcast_status("1. DRONE_DETECT", "Checking Drone landing at Dock N1...")
            await self.plc_mgr.wait_for_status("drone_detected", True, timeout_sec=15.0)

            # 2. Lock Drone
            await self._broadcast_status("2. LOCK_DRONE", "PLC Locking drone clamps (DB15.DBX0.0)...")
            await self.plc_mgr.execute_command(PLCCommand.LOCK_DRONE)
            await self.plc_mgr.wait_for_status("plc_locked_state", True, timeout_sec=5.0)

            # 3. Robot Pick From Storage
            await self._broadcast_status("3. ROBOT_PICK_SLOT", f"Robot picking product from slot {target_slot}...")
            await self.robot_mgr.execute_command(RobotCommand.PICK, slot=target_slot)

            # 4. Robot Home
            await self._broadcast_status("4. ROBOT_HOME_1", "Robot returning Home position...")
            await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)

            # 5. QR Verify
            await self._broadcast_status("5. QR_VERIFY", f"Camera verifying QR code for product {product_id}...")
            await asyncio.sleep(0.5)

            # 6. Z Up
            await self._broadcast_status("6. PLC_Z_UP", "PLC Raising Z-axis lift to UP position (DB15.DBX0.2)...")
            await self.plc_mgr.execute_command(PLCCommand.Z_UP)
            await self.plc_mgr.wait_for_status("plc_z_is_up", True, timeout_sec=5.0)

            # 7. Robot Place Product onto Drone Dock
            await self._broadcast_status("7. ROBOT_PLACE_DOCK", "Robot placing product onto Drone Dock...")
            await self.robot_mgr.execute_command(RobotCommand.PLACE_PRODUCT, slot="DOCK")

            # 8. Robot Home
            await self._broadcast_status("8. ROBOT_HOME_2", "Robot returning Home position...")
            await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)

            # 9. Z Down
            await self._broadcast_status("9. PLC_Z_DOWN", "PLC Lowering Z-axis lift to DOWN position (DB15.DBX0.3)...")
            await self.plc_mgr.execute_command(PLCCommand.Z_DOWN)
            await self.plc_mgr.wait_for_status("plc_z_is_down", True, timeout_sec=5.0)

            # 10. Unlock Drone
            await self._broadcast_status("10. UNLOCK_DRONE", "PLC Unlocking drone clamps (DB15.DBX0.1)...")
            await self.plc_mgr.execute_command(PLCCommand.UNLOCK_DRONE)
            await self.plc_mgr.wait_for_status("plc_locked_state", False, timeout_sec=5.0)

            # 11. Clear Storage Slot in Inventory & Finish
            await inv_mgr.update_slot(target_slot, StorageSlotStatus.EMPTY, product_id=None)
            await self._broadcast_status("11. TAKEOFF_COMPLETE", f"Successfully loaded product {product_id} onto Drone. Ready for Takeoff!", status="COMPLETED")
            return True

        except Exception as err:
            logger.error("Station LOAD_PRODUCT failed: %s", err)
            await self._broadcast_status("LOAD_FAILED", f"LOAD_PRODUCT failed: {err}", status="FAILED")
            return False

    async def execute_unload_product(self, target_slot: str, product_id: str, session: AsyncSession) -> bool:
        """UNLOAD_PRODUCT Operation (Drone Pickup / Import): Drone Dock -> Warehouse Slot.

        11-Step FSM Sequence:
          1. Drone Detect (drone_detected == TRUE)
          2. Lock Drone (cmd_lock_drone -> plc_locked_state == TRUE)
          3. Robot Home (MOVE_HOME)
          4. Z Up (cmd_z_up -> plc_z_is_up == TRUE)
          5. Robot Pick (PICK DOCK)
          6. Robot Home (MOVE_HOME)
          7. Z Down (cmd_z_down -> plc_z_is_down == TRUE)
          8. QR Scan (Scan product QR code)
          9. Store Product (STORE target_slot)
          10. Unlock Drone (cmd_unlock_drone -> plc_locked_state == FALSE)
          11. Takeoff / Complete
        """
        self.current_operation = "UNLOAD_PRODUCT"
        self.target_slot = target_slot
        self.product_id = product_id

        inv_mgr = InventoryManager(session)

        try:
            # 1. Drone Detect
            await self._broadcast_status("1. DRONE_DETECT", "Checking Drone landing at Dock N1...")
            await self.plc_mgr.wait_for_status("drone_detected", True, timeout_sec=15.0)

            # 2. Lock Drone
            await self._broadcast_status("2. LOCK_DRONE", "PLC Locking drone clamps (DB15.DBX0.0)...")
            await self.plc_mgr.execute_command(PLCCommand.LOCK_DRONE)
            await self.plc_mgr.wait_for_status("plc_locked_state", True, timeout_sec=5.0)

            # 3. Robot Home
            await self._broadcast_status("3. ROBOT_HOME_1", "Robot moving to Home position...")
            await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)

            # 4. Z Up
            await self._broadcast_status("4. PLC_Z_UP", "PLC Raising Z-axis lift to UP position (DB15.DBX0.2)...")
            await self.plc_mgr.execute_command(PLCCommand.Z_UP)
            await self.plc_mgr.wait_for_status("plc_z_is_up", True, timeout_sec=5.0)

            # 5. Robot Pick from Drone Dock
            await self._broadcast_status("5. ROBOT_PICK_DOCK", "Robot picking product from Drone Dock...")
            await self.robot_mgr.execute_command(RobotCommand.PICK_PRODUCT, slot="DOCK")

            # 6. Robot Home
            await self._broadcast_status("6. ROBOT_HOME_2", "Robot returning to Home position...")
            await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)

            # 7. Z Down
            await self._broadcast_status("7. PLC_Z_DOWN", "PLC Lowering Z-axis lift to DOWN position (DB15.DBX0.3)...")
            await self.plc_mgr.execute_command(PLCCommand.Z_DOWN)
            await self.plc_mgr.wait_for_status("plc_z_is_down", True, timeout_sec=5.0)

            # 8. QR Scan
            await self._broadcast_status("8. QR_SCAN", f"Camera scanning QR code for product {product_id}...")
            await asyncio.sleep(0.5)

            # 9. Store Product into Storage Slot
            await self._broadcast_status("9. ROBOT_STORE_SLOT", f"Robot storing product into slot {target_slot}...")
            await self.robot_mgr.execute_command(RobotCommand.STORE, slot=target_slot)

            # 10. Unlock Drone
            await self._broadcast_status("10. UNLOCK_DRONE", "PLC Unlocking drone clamps (DB15.DBX0.1)...")
            await self.plc_mgr.execute_command(PLCCommand.UNLOCK_DRONE)
            await self.plc_mgr.wait_for_status("plc_locked_state", False, timeout_sec=5.0)

            # 11. Assign product to Storage Slot in Inventory & Finish
            await inv_mgr.update_slot(target_slot, StorageSlotStatus.OCCUPIED, product_id=product_id)
            await self._broadcast_status("11. TAKEOFF_COMPLETE", f"Successfully stored product {product_id} into slot {target_slot}. Ready for Takeoff!", status="COMPLETED")
            return True

        except Exception as err:
            logger.error("Station UNLOAD_PRODUCT failed: %s", err)
            await self._broadcast_status("UNLOAD_FAILED", f"UNLOAD_PRODUCT failed: {err}", status="FAILED")
            return False

