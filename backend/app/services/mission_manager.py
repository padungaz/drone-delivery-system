import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import IntralogisticsMissionRecord, SystemLogRecord
from app.models.schemas import (
    PLCCommand,
    RobotCommand,
    StorageSlotStatus,
    IntralogisticsMissionResponse,
)
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.inventory_manager import InventoryManager

logger = logging.getLogger(__name__)


class MissionManager:
    """Master Intralogistics Mission Orchestrator.
    Executes automated coordination between UAV, PLC S7-1200, FAIRINO Robot, and Inventory.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.plc_mgr = PLCManager.get_instance()
        self.robot_mgr = RobotManager.get_instance()
        self.inventory_mgr = InventoryManager(session)

    async def log_event(self, source: str, message: str, log_type: str = "MISSION_LOG") -> None:
        logger.info("[%s] %s", source, message)
        log_entry = SystemLogRecord(
            log_type=log_type,
            source=source,
            message=message,
            created_at=datetime.utcnow(),
        )
        self.session.add(log_entry)
        await self.session.commit()

    async def execute_drone_pickup(self, drone_id: str, product_id: str) -> IntralogisticsMissionRecord:
        """Flow 8: DRONE_PICKUP (Drone brings product to warehouse for storage)"""
        mission = IntralogisticsMissionRecord(
            mission_type="DRONE_PICKUP",
            drone_id=drone_id,
            product_id=product_id,
            state="STARTED",
            step_details="1. Mission sent to UAV",
            created_at=datetime.utcnow(),
        )
        self.session.add(mission)
        await self.session.commit()
        await self.session.refresh(mission)

        await self.log_event("SERVER", f"Started DRONE_PICKUP mission #{mission.id} for product {product_id}")

        # Step 2: Drone landing simulation / pad arrival
        mission.state = "TAKEOFF_AND_FLYING"
        mission.step_details = "2. Drone flying to warehouse pad"
        await self.session.commit()
        await asyncio.sleep(0.5)

        # Step 3 & 4: Touchdown & PLC Sensor detect
        self.plc_mgr.set_drone_detected(True)
        mission.state = "TOUCHDOWN"
        mission.step_details = "3-5. Drone touched down on pad. Sensor detected."
        await self.log_event("PLC", "Drone detected on landing pad")
        await self.session.commit()

        # Step 6 & 7: PLC Lock Drone
        await self.plc_mgr.execute_command(PLCCommand.LOCK_DRONE)
        mission.state = "DRONE_LOCKED"
        mission.step_details = "6-7. PLC locked drone clamps (X & Y)."
        await self.log_event("PLC", "DRONE_LOCKED confirmed by PLC")
        await self.session.commit()

        # Step 8 & 9: Robot to Home
        await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        mission.step_details = "8-9. FAIRINO Robot initialized at HOME position."
        await self.log_event("ROBOT", "Robot moved to HOME position")

        # Step 10 & 11: Request Z_UP & PLC Z axis UP
        await self.robot_mgr.execute_command(RobotCommand.REQUEST_Z_UP)
        await self.plc_mgr.execute_command(PLCCommand.Z_UP)
        mission.step_details = "10-11. Lift Z-axis raised to UP position."
        await self.log_event("PLC", "Z_UP completed")

        # Step 12: Robot pick product from Drone
        await self.robot_mgr.execute_command(RobotCommand.PICK_PRODUCT)
        mission.step_details = "12. Robot picked product from Drone."
        await self.log_event("ROBOT", f"Pick completed for product {product_id}")

        # Step 13 & 14 & 15: Robot Home & Z_DOWN
        await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        await self.robot_mgr.execute_command(RobotCommand.REQUEST_Z_DOWN)
        await self.plc_mgr.execute_command(PLCCommand.Z_DOWN)
        mission.step_details = "13-15. Robot returned HOME and Z-axis lowered."
        await self.log_event("SERVER", "DRONE_PICKUP_COMPLETE")

        # Step 16-20: Find free slot and store in warehouse
        free_slot = await self.inventory_mgr.find_available_slot()
        if free_slot:
            target_slot = free_slot.slot_name
            mission.target_slot = target_slot
            await self.robot_mgr.execute_command(RobotCommand.STORE, slot=target_slot)
            await self.inventory_mgr.update_slot(
                slot_name=target_slot,
                status=StorageSlotStatus.OCCUPIED,
                product_id=product_id,
                qr_code=product_id,
            )
            mission.state = "MISSION_COMPLETE"
            mission.step_details = f"16-20. Product stored into slot {target_slot} successfully."
            await self.log_event("ROBOT", f"STORE_PRODUCT({target_slot}) completed")
        else:
            mission.state = "ERROR_NO_FREE_SLOT"
            mission.step_details = "Warehouse full! No free slot available."
            await self.log_event("SERVER", "No free slot available for storage", log_type="ERROR_LOG")

        # Step 21: Unlock Drone for return flight
        await self.plc_mgr.execute_command(PLCCommand.UNLOCK_DRONE)
        await self.session.commit()
        await self.session.refresh(mission)
        return mission

    async def execute_drone_delivery(self, drone_id: str, product_id: str) -> IntralogisticsMissionRecord:
        """Flow 9: DRONE_DELIVERY (Robot picks product from slot & loads onto Drone for delivery)"""
        mission = IntralogisticsMissionRecord(
            mission_type="DRONE_DELIVERY",
            drone_id=drone_id,
            product_id=product_id,
            state="STARTED",
            step_details="1. Received delivery request",
            created_at=datetime.utcnow(),
        )
        self.session.add(mission)
        await self.session.commit()
        await self.session.refresh(mission)

        await self.log_event("SERVER", f"Started DRONE_DELIVERY mission #{mission.id} for product {product_id}")

        # Step 2: Find product location in storage
        slot_record = await self.inventory_mgr.find_slot_by_product_id(product_id)
        if not slot_record:
            mission.state = "ERROR_PRODUCT_NOT_FOUND"
            mission.step_details = f"Product {product_id} not found in warehouse storage slots!"
            await self.log_event("SERVER", f"Product {product_id} not found in inventory", log_type="ERROR_LOG")
            await self.session.commit()
            return mission

        target_slot = slot_record.slot_name
        mission.target_slot = target_slot

        # Step 3, 4, 5: Robot pick product from slot & Home
        await self.robot_mgr.execute_command(RobotCommand.PICK, slot=target_slot)
        await self.inventory_mgr.update_slot(slot_name=target_slot, status=StorageSlotStatus.EMPTY)
        await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        mission.step_details = f"3-5. Robot picked product {product_id} from slot {target_slot}."
        await self.log_event("ROBOT", f"GET_PRODUCT({target_slot}) completed")

        # Step 6 & 7 & 8: Drone landing & PLC LOCK_DRONE
        self.plc_mgr.set_drone_detected(True)
        await self.plc_mgr.execute_command(PLCCommand.LOCK_DRONE)
        mission.step_details = "6-8. Drone landed and locked by PLC clamps."
        await self.log_event("PLC", "Drone locked for loading")

        # Step 9 & 10 & 11: Request Z_UP & Robot place product on Drone
        await self.robot_mgr.execute_command(RobotCommand.REQUEST_Z_UP)
        await self.plc_mgr.execute_command(PLCCommand.Z_UP)
        await self.robot_mgr.execute_command(RobotCommand.PLACE_PRODUCT)
        mission.step_details = f"9-11. Robot placed product {product_id} onto Drone."
        await self.log_event("ROBOT", f"Placed product {product_id} on Drone")

        # Step 12 & 13 & 14 & 15: Robot Home, Z_DOWN, PLC DRONE_LOADED_SUCCESS
        await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        await self.robot_mgr.execute_command(RobotCommand.REQUEST_Z_DOWN)
        await self.plc_mgr.execute_command(PLCCommand.Z_DOWN)
        await self.log_event("PLC", "DRONE_LOADED_SUCCESS")

        # Step 16: Unlock Drone & grant takeoff
        await self.plc_mgr.execute_command(PLCCommand.UNLOCK_DRONE)
        mission.state = "MISSION_COMPLETE"
        mission.step_details = "16. Drone unlocked and cleared for delivery takeoff!"
        await self.log_event("SERVER", "DRONE_DELIVERY mission complete — UAV cleared for takeoff")

        await self.session.commit()
        await self.session.refresh(mission)
        return mission
