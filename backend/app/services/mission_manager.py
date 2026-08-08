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
from app.services.qr_scanner_service import QRScannerService
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class MissionManager:
    """Master Intralogistics Mission Orchestrator — Handshake Signal Protocol.

    Architecture: Sequential Command/Done Handshake with Safety Interlocks
    =======================================================================
    Backend acts as the Master Orchestrator. It sends commands to PLC and Robot
    one at a time, waiting for each device to complete before proceeding to the
    next step. If any device reports an ERROR or TIMEOUT, the sequence is
    IMMEDIATELY ABORTED to prevent mechanical collisions.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.plc_mgr = PLCManager.get_instance()
        self.robot_mgr = RobotManager.get_instance()
        self.inventory_mgr = InventoryManager(session)
        self.qr_svc = QRScannerService.get_instance()

    async def _notify_mission_progress(self, mission: IntralogisticsMissionRecord) -> None:
        """Broadcast mission progress state to frontend WebSockets."""
        try:
            await system_ws_manager.broadcast("MISSION_PROGRESS", {
                "mission": {
                    "id": mission.id,
                    "mission_type": mission.mission_type,
                    "drone_id": mission.drone_id,
                    "product_id": mission.product_id,
                    "target_slot": mission.target_slot,
                    "state": mission.state,
                    "step_details": mission.step_details,
                }
            })
        except Exception:
            pass

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

    async def validate_docking_eligibility(self, location_type: str = "WAREHOUSE_PAD") -> tuple[bool, str]:
        """Dual Safety Check for Intralogistics Execution:
        1. Location must be WAREHOUSE_PAD (not CUSTOMER_PICKUP or CUSTOMER_DROP).
        2. PLC must confirm drone presence (drone_detected == True or simulator_mode == True).
        """
        loc_str = str(location_type).upper()
        if loc_str not in ("WAREHOUSE_PAD", "HOME", "WAREHOUSE", "LANDINGLOCATION.WAREHOUSE_PAD"):
            return False, f"Vị trí hạ cánh ({location_type}) không phải Trạm Docking Kho (WAREHOUSE_PAD). Từ chối chạy PLC/Robot."

        await self.plc_mgr.read_plc_status()
        plc_status = self.plc_mgr.get_status()
        if not (plc_status.drone_detected or plc_status.simulator_mode):
            return False, "Cảm biến PLC chưa phát hiện Drone trên Pad kho (drone_detected = False). Từ chối chạy PLC/Robot."

        return True, "Xác thực thành công UAV hạ cánh đúng Trạm Docking Kho."

    async def execute_drone_pickup(
        self, drone_id: str, product_id: str, location_type: str = "WAREHOUSE_PAD"
    ) -> IntralogisticsMissionRecord:
        """Flow Nhập Kho (DRONE_PICKUP) — Safety Interlocked Sequential Handshake:

        1. Check Docking Safety Interlock (Location MUST be WAREHOUSE_PAD & PLC drone_detected)
        2. PLC LOCK_DRONE -> Check success
        3. ROBOT MOVE_HOME -> Check success
        4. PLC Z_UP -> Check success (Must be UP before robot enters pad area)
        5. ROBOT PICK_PRODUCT (from UAV) -> Check success
        6. ROBOT MOVE_HOME -> Check success (Robot retracts before lowering Z-axis)
        7. PLC Z_DOWN -> Check success
        8. Camera ON -> Scan QR -> Find available storage slot
        9. ROBOT STORE (place into storage slot A1..C3) -> Check success
        10. Camera OFF
        11. PLC UNLOCK_DRONE -> Complete
        """
        # Ensure camera is initially OFF
        self.qr_svc.stop_camera_scanner()

        mission = IntralogisticsMissionRecord(
            mission_type="DRONE_PICKUP",
            drone_id=drone_id,
            product_id=product_id,
            state="STARTED",
            step_details="1. UAV arrived on pad. Camera OFF.",
            created_at=datetime.utcnow(),
        )
        self.session.add(mission)
        await self.session.commit()
        await self.session.refresh(mission)

        # Dual Safety Check: Ensure UAV is at Warehouse Pad and PLC detects drone
        eligible, reason = await self.validate_docking_eligibility(location_type)
        if not eligible:
            mission.state = "REJECTED_LOCATION"
            mission.step_details = f"🛑 TỪ CHỐI THỰC THI: {reason}"
            await self.log_event("SERVER", f"Mission #{mission.id} REJECTED: {reason}", log_type="ERROR_LOG")
            await self.session.commit()
            return mission

        await self.log_event("SERVER", f"Started DRONE_PICKUP mission #{mission.id} for product {product_id}")

        # Step 1: PLC LOCK_DRONE
        plc_res = await self.plc_mgr.execute_command(PLCCommand.LOCK_DRONE)
        if plc_res.plc_error:
            return await self._abort_mission(mission, "Step 1: PLC LOCK_DRONE failed or E-Stop triggered!")

        mission.state = "DOCK_LOCKED"
        mission.step_details = "2. PLC đã khóa cố định Drone trên pad (PLC_LOCK_DONE)."
        await self.log_event("PLC", "Drone locked on pad (PLC_LOCK_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 2: ROBOT MOVE_HOME
        robot_res = await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        if robot_res.state == "ERROR":
            return await self._abort_mission(mission, "Step 2: Robot MOVE_HOME failed!")

        mission.step_details = "3. Robot đã về vị trí HOME (ROBOT_DONE)."
        await self.log_event("ROBOT", "Robot returned to HOME position (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 3: PLC Z_UP (Safety Interlock: Must succeed before robot enters pad)
        plc_res = await self.plc_mgr.execute_command(PLCCommand.Z_UP)
        if plc_res.plc_error or plc_res.z_axis != "UP":
            return await self._abort_mission(mission, "Step 3: PLC Z_UP failed! Trục Z chưa nâng. Aborting for collision safety.")

        mission.step_details = "4. PLC đã nâng trục Z lên vị trí trên (PLC_Z_UP_DONE)."
        await self.log_event("PLC", "Z_UP completed (PLC_Z_UP_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 4: ROBOT PICK_PRODUCT from UAV
        robot_res = await self.robot_mgr.execute_command(RobotCommand.PICK_PRODUCT)
        if robot_res.state == "ERROR":
            return await self._abort_mission(mission, "Step 4: Robot PICK_PRODUCT from UAV failed!")

        mission.state = "ROBOT_PICKING"
        mission.step_details = f"5. Robot đã gắp sản phẩm {product_id} từ UAV (ROBOT_DONE)."
        await self.log_event("ROBOT", f"Picked product {product_id} from UAV (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 5: ROBOT MOVE_HOME (Retract from pad before lowering Z-axis)
        robot_res = await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        if robot_res.state == "ERROR":
            return await self._abort_mission(mission, "Step 5: Robot MOVE_HOME failed while carrying product!")

        mission.step_details = f"6. Robot mang {product_id} rút về vị trí HOME an toàn (ROBOT_DONE)."
        await self.log_event("ROBOT", f"Robot carrying {product_id} returned to HOME (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 6: PLC Z_DOWN (Lower Z-axis after robot retracts)
        plc_res = await self.plc_mgr.execute_command(PLCCommand.Z_DOWN)
        if plc_res.plc_error:
            return await self._abort_mission(mission, "Step 6: PLC Z_DOWN failed!")

        mission.step_details = "7. PLC đã hạ trục Z xuống vị trí dưới (PLC_Z_DOWN_DONE)."
        await self.log_event("PLC", "Z_DOWN completed (PLC_Z_DOWN_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 7: Camera ON -> QR Scan -> Find available storage slot
        self.qr_svc.start_camera_scanner()
        await self.qr_svc.notify_status_ws()
        await self.log_event("CAMERA", "Backend Camera TURNED ON to scan product QR code")
        mission.step_details = "8. Camera ON -> Đang quét mã QR sản phẩm."
        await self.session.commit()
        await self._notify_mission_progress(mission)
        await asyncio.sleep(2.0)  # Pause for frontend live camera video stream preview

        scan_res = await self.qr_svc.process_qr_code(product_id, source="FSM_PICKUP_SCAN")
        free_slot = await self.inventory_mgr.find_available_slot()

        if free_slot or scan_res.get("slot_name"):
            target_slot = scan_res.get("slot_name") or (free_slot.slot_name if free_slot else "A1")
            mission.target_slot = target_slot

            # Step 8: ROBOT STORE (cất vào ô kho)
            robot_res = await self.robot_mgr.execute_command(RobotCommand.STORE, slot=target_slot)
            if robot_res.state == "ERROR":
                self.qr_svc.stop_camera_scanner()
                await self.qr_svc.notify_status_ws()
                return await self._abort_mission(mission, f"Step 8: Robot STORE into slot {target_slot} failed!")

            await self.inventory_mgr.update_slot(
                slot_name=target_slot,
                status=StorageSlotStatus.OCCUPIED,
                product_id=product_id,
                qr_code=product_id,
            )
            mission.state = "STORAGE_PLACED"
            mission.step_details = f"9. Robot đã cất sản phẩm vào ô {target_slot} (ROBOT_DONE)."
            await self.log_event("ROBOT", f"Stored product into slot {target_slot} (ROBOT_DONE)")
            await self.session.commit()
            await self._notify_mission_progress(mission)

            # Step 9: Camera OFF
            self.qr_svc.stop_camera_scanner()
            await self.qr_svc.notify_status_ws()
            await self.log_event("CAMERA", "Backend Camera TURNED OFF after placement.")

            # Step 10: PLC UNLOCK_DRONE -> Complete
            plc_res = await self.plc_mgr.execute_command(PLCCommand.UNLOCK_DRONE)
            if plc_res.plc_error:
                return await self._abort_mission(mission, "Step 10: PLC UNLOCK_DRONE failed!")

            mission.state = "COMPLETED"
            mission.step_details = "10. PLC đã mở khóa Drone (PLC_UNLOCK_DONE). Nhiệm vụ Nhập Kho HOÀN THÀNH!"
            await self.log_event("SERVER", f"DRONE_PICKUP Mission #{mission.id} COMPLETED")
            await self.session.commit()
            await self._notify_mission_progress(mission)
        else:
            self.qr_svc.stop_camera_scanner()
            mission.state = "ERROR_NO_FREE_SLOT"
            mission.step_details = "Warehouse full! No free slot available."
            await self.log_event("SERVER", "No free slot available for storage", log_type="ERROR_LOG")

        await self.session.commit()
        await self.session.refresh(mission)
        return mission

    async def execute_drone_delivery(
        self, drone_id: str, product_id: str, location_type: str = "WAREHOUSE_PAD"
    ) -> IntralogisticsMissionRecord:
        """Flow Xuất Kho (DRONE_DELIVERY) — Safety Interlocked Sequential Handshake:

        1. Check Docking Safety Interlock (Location MUST be WAREHOUSE_PAD & PLC drone_detected)
        2. PLC LOCK_DRONE -> Check success
        3. Find product location in storage
        4. ROBOT PICK (from storage slot A1..C3) -> Check success
        5. ROBOT MOVE_HOME -> Check success
        6. Camera ON -> Verify product
        7. PLC Z_UP -> Check success (Safety Interlock: Must be UP before robot places on UAV)
        8. ROBOT PLACE_PRODUCT (onto UAV) -> Check success
        9. ROBOT MOVE_HOME -> Check success (Robot retracts before lowering Z-axis)
        10. Camera OFF -> Turn off camera immediately after placement
        11. PLC Z_DOWN -> Check success
        12. PLC UNLOCK_DRONE -> Complete
        """
        # Ensure camera is initially OFF
        self.qr_svc.stop_camera_scanner()

        mission = IntralogisticsMissionRecord(
            mission_type="DRONE_DELIVERY",
            drone_id=drone_id,
            product_id=product_id,
            state="STARTED",
            step_details="1. Delivery request started. Camera OFF.",
            created_at=datetime.utcnow(),
        )
        self.session.add(mission)
        await self.session.commit()
        await self.session.refresh(mission)

        # Dual Safety Check: Ensure UAV is at Warehouse Pad and PLC detects drone
        eligible, reason = await self.validate_docking_eligibility(location_type)
        if not eligible:
            mission.state = "REJECTED_LOCATION"
            mission.step_details = f"🛑 TỪ CHỐI THỰC THI: {reason}"
            await self.log_event("SERVER", f"Mission #{mission.id} REJECTED: {reason}", log_type="ERROR_LOG")
            await self.session.commit()
            return mission

        await self.log_event("SERVER", f"Started DRONE_DELIVERY mission #{mission.id} for product {product_id}")

        # Step 1: PLC LOCK_DRONE
        plc_res = await self.plc_mgr.execute_command(PLCCommand.LOCK_DRONE)
        if plc_res.plc_error:
            return await self._abort_mission(mission, "Step 1: PLC LOCK_DRONE failed!")

        mission.state = "DOCK_LOCKED"
        mission.step_details = "2. PLC đã khóa cố định Drone trên pad (PLC_LOCK_DONE)."
        await self.log_event("PLC", "Drone locked on pad (PLC_LOCK_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 2: Find product location in storage
        slot_record = await self.inventory_mgr.find_slot_by_product_id(product_id)
        if not slot_record:
            mission.state = "ERROR_PRODUCT_NOT_FOUND"
            mission.step_details = f"Product {product_id} not found in warehouse storage slots!"
            await self.log_event("SERVER", f"Product {product_id} not found in inventory", log_type="ERROR_LOG")
            await self.session.commit()
            await self._notify_mission_progress(mission)
            return mission

        target_slot = slot_record.slot_name
        mission.target_slot = target_slot

        # Step 3: ROBOT PICK from storage slot
        robot_res = await self.robot_mgr.execute_command(RobotCommand.PICK, slot=target_slot)
        if robot_res.state == "ERROR":
            return await self._abort_mission(mission, f"Step 3: Robot PICK from slot {target_slot} failed!")

        await self.inventory_mgr.update_slot(slot_name=target_slot, status=StorageSlotStatus.EMPTY)
        mission.state = "ROBOT_PICKING"
        mission.step_details = f"3. Robot đã lấy sản phẩm {product_id} từ ô {target_slot} (ROBOT_DONE)."
        await self.log_event("ROBOT", f"Picked product {product_id} from slot {target_slot} (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 4: ROBOT MOVE_HOME
        robot_res = await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        if robot_res.state == "ERROR":
            return await self._abort_mission(mission, "Step 4: Robot MOVE_HOME failed!")

        mission.step_details = f"4. Robot mang {product_id} về vị trí HOME (ROBOT_DONE)."
        await self.log_event("ROBOT", f"Robot holding {product_id} returned to HOME (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 5: Camera ON -> Verify product
        self.qr_svc.start_camera_scanner()
        await self.qr_svc.notify_status_ws()
        await self.log_event("CAMERA", f"Backend Camera TURNED ON -> Verified robot carrying product {product_id}")
        mission.step_details = f"5. Camera ON -> Đã xác nhận robot đang mang sản phẩm {product_id}."
        await self.session.commit()
        await self._notify_mission_progress(mission)
        await asyncio.sleep(2.0)

        # Step 6: PLC Z_UP (Safety Interlock: Must succeed before robot enters pad)
        plc_res = await self.plc_mgr.execute_command(PLCCommand.Z_UP)
        if plc_res.plc_error or plc_res.z_axis != "UP":
            self.qr_svc.stop_camera_scanner()
            await self.qr_svc.notify_status_ws()
            return await self._abort_mission(mission, "Step 6: PLC Z_UP failed! Trục Z chưa nâng. Aborting for collision safety.")

        mission.step_details = "6. PLC đã nâng trục Z lên (PLC_Z_UP_DONE)."
        await self.log_event("PLC", "Z_UP completed (PLC_Z_UP_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 7: ROBOT PLACE_PRODUCT onto UAV
        robot_res = await self.robot_mgr.execute_command(RobotCommand.PLACE_PRODUCT)
        if robot_res.state == "ERROR":
            self.qr_svc.stop_camera_scanner()
            await self.qr_svc.notify_status_ws()
            return await self._abort_mission(mission, "Step 7: Robot PLACE_PRODUCT onto UAV failed!")

        mission.step_details = f"7. Robot đã đặt sản phẩm {product_id} lên UAV (ROBOT_DONE)."
        await self.log_event("ROBOT", f"Placed product {product_id} onto UAV (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 8: ROBOT MOVE_HOME (Retract from pad before closing hatch)
        robot_res = await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        if robot_res.state == "ERROR":
            self.qr_svc.stop_camera_scanner()
            await self.qr_svc.notify_status_ws()
            return await self._abort_mission(mission, "Step 8: Robot MOVE_HOME failed after placing product!")

        mission.step_details = "8. Robot đã rút về vị trí HOME an toàn (ROBOT_DONE)."
        await self.log_event("ROBOT", "Robot returned to HOME after placing product (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 9: Camera OFF (Turn off camera immediately after placement complete)
        self.qr_svc.stop_camera_scanner()
        await self.qr_svc.notify_status_ws()
        await self.log_event("CAMERA", "Backend Camera TURNED OFF after placement.")

        # Step 10: PLC Z_DOWN
        plc_res = await self.plc_mgr.execute_command(PLCCommand.Z_DOWN)
        if plc_res.plc_error:
            return await self._abort_mission(mission, "Step 10: PLC Z_DOWN failed!")

        mission.state = "STORAGE_PLACED"
        mission.step_details = "9. PLC đã hạ trục Z xuống (PLC_Z_DOWN_DONE)."
        await self.log_event("PLC", "Z_DOWN completed (PLC_Z_DOWN_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 11: PLC UNLOCK_DRONE -> Complete
        plc_res = await self.plc_mgr.execute_command(PLCCommand.UNLOCK_DRONE)
        if plc_res.plc_error:
            return await self._abort_mission(mission, "Step 11: PLC UNLOCK_DRONE failed!")

        mission.state = "COMPLETED"
        mission.step_details = "10-11. PLC đã mở khóa Drone. Camera OFF. Nhiệm vụ Xuất Kho HOÀN THÀNH!"
        await self.log_event("SERVER", f"DRONE_DELIVERY Mission #{mission.id} COMPLETED")

        await self.session.commit()
        await self._notify_mission_progress(mission)
        await self.session.refresh(mission)
        return mission

    async def _abort_mission(self, mission: IntralogisticsMissionRecord, reason: str) -> IntralogisticsMissionRecord:
        """Helper to safely abort mission on hardware failure or timeout."""
        logger.error("🛑 ABORTING MISSION #%d: %s", mission.id, reason)
        mission.state = "FAILED"
        mission.step_details = f"🛑 DỪNG KHẨN CẤP: {reason}"
        await self.log_event("SERVER", f"Mission #{mission.id} ABORTED: {reason}", log_type="ERROR_LOG")
        await self.session.commit()
        await self._notify_mission_progress(mission)
        await self.session.refresh(mission)
        return mission

    async def pause_mission(self, mission_id: Optional[int] = None) -> Optional[IntralogisticsMissionRecord]:
        mission = await self.get_active_mission() if not mission_id else await self.session.get(IntralogisticsMissionRecord, mission_id)
        if mission and mission.state not in ("COMPLETED", "FAILED", "ERROR_NO_FREE_SLOT", "ERROR_PRODUCT_NOT_FOUND"):
            mission.state = "PAUSED"
            mission.step_details = f"⏸️ Nhiệm vụ #{mission.id} đã được tạm dừng bởi Operator."
            await self.log_event("SERVER", f"Mission #{mission.id} PAUSED by Operator")
            await self.session.commit()
            await self._notify_mission_progress(mission)
            await self.session.refresh(mission)
            return mission
        return None

    async def resume_mission(self, mission_id: Optional[int] = None) -> Optional[IntralogisticsMissionRecord]:
        mission = await self.session.get(IntralogisticsMissionRecord, mission_id) if mission_id else await self.get_active_mission()
        if not mission:
            stmt = select(IntralogisticsMissionRecord).where(IntralogisticsMissionRecord.state == "PAUSED").order_by(IntralogisticsMissionRecord.id.desc())
            res = await self.session.execute(stmt)
            mission = res.scalars().first()

        if mission and mission.state == "PAUSED":
            mission.state = "DOCK_LOCKED"
            mission.step_details = f"▶️ Nhiệm vụ #{mission.id} được khôi phục tiếp tục."
            await self.log_event("SERVER", f"Mission #{mission.id} RESUMED by Operator")
            await self.session.commit()
            await self._notify_mission_progress(mission)
            await self.session.refresh(mission)
            return mission
        return None

    async def manual_override_qr(self, product_id: str, mission_id: Optional[int] = None) -> Optional[IntralogisticsMissionRecord]:
        mission = await self.get_active_mission() if not mission_id else await self.session.get(IntralogisticsMissionRecord, mission_id)
        if mission:
            mission.product_id = product_id
            mission.step_details = f"✏️ Operator đã nhập mã QR thủ công: {product_id}"
            await self.log_event("SERVER", f"Manual QR Override for Mission #{mission.id}: {product_id}")
            await self.session.commit()
            await self._notify_mission_progress(mission)
            await self.session.refresh(mission)
            return mission
        return None

    async def get_all_missions(self) -> List[IntralogisticsMissionRecord]:
        stmt = select(IntralogisticsMissionRecord).order_by(IntralogisticsMissionRecord.id.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_active_mission(self) -> Optional[IntralogisticsMissionRecord]:
        stmt = select(IntralogisticsMissionRecord).where(
            IntralogisticsMissionRecord.state.notin_(["COMPLETED", "FAILED", "ERROR_NO_FREE_SLOT", "ERROR_PRODUCT_NOT_FOUND"])
        ).order_by(IntralogisticsMissionRecord.id.desc())
        res = await self.session.execute(stmt)
        return res.scalars().first()

