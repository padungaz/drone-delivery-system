import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import IntralogisticsMissionRecord, SystemLogRecord, DeliveryRequestRecord
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

    def _serialize_mission(self, mission: IntralogisticsMissionRecord) -> dict:
        station_proc = json.loads(mission.station_process_json) if mission.station_process_json else None
        uav_miss = json.loads(mission.uav_mission_json) if mission.uav_mission_json else None
        return {
            "id": mission.id,
            "mission_type": mission.mission_type,
            "drone_id": mission.drone_id,
            "product_id": mission.product_id,
            "target_slot": mission.target_slot,
            "state": mission.state,
            "step_details": mission.step_details,
            "station_process": station_proc,
            "uav_mission": uav_miss,
            "created_at": mission.created_at.isoformat() if mission.created_at else "",
            "updated_at": mission.updated_at.isoformat() if mission.updated_at else "",
        }

    async def _notify_mission_progress(self, mission: IntralogisticsMissionRecord) -> None:
        """Broadcast mission progress state to frontend WebSockets."""
        try:
            m_dict = self._serialize_mission(mission)
            await system_ws_manager.broadcast("MISSION_PROGRESS", {
                "mission": m_dict,
                "mission_id": mission.id,
                "type": mission.mission_type,
                "drone_id": mission.drone_id,
                "product_id": mission.product_id,
                "state": mission.state,
                "step_details": mission.step_details,
                "station_process": m_dict.get("station_process"),
                "uav_mission": m_dict.get("uav_mission"),
            })
        except Exception as err:
            logger.error("Error in _notify_mission_progress: %s", err)

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

    def _build_pickup_structures(self, drone_id: str, product_id: str, target_slot: Optional[str] = "A1") -> tuple[dict, dict]:
        station_proc = {
            "station_id": "STATION_WH_001",
            "status": "in_progress",
            "current_step": "plc_lock_drone",
            "steps": [
                {"step": 1, "device": "PLC", "action": "lock_drone", "description": "PLC Khóa kẹp cố định chân Drone sau khi hạ cánh", "status": "waiting"},
                {"step": 2, "device": "PLC", "action": "z_axis_up", "description": "PLC nâng trục Z bàn nâng lên vị trí gắp hàng", "status": "waiting"},
                {"step": 3, "device": "CAMERA", "action": "scan_qr_code", "description": f"Camera quét & xác nhận mã QR sản phẩm {product_id}", "status": "waiting"},
                {"step": 4, "device": "ROBOT", "action": "pick_from_uav", "description": "Robot gắp hàng từ gá Drone", "status": "waiting"},
                {"step": 5, "device": "ROBOT", "action": "store_to_slot", "target_slot": target_slot or "A1", "description": f"Robot lưu trữ sản phẩm vào ô kho {target_slot or 'A1'}", "status": "waiting"},
                {"step": 6, "device": "PLC", "action": "z_axis_down", "description": "PLC hạ trục Z bàn nâng về vị trí ban đầu", "status": "waiting"},
                {"step": 7, "device": "PLC", "action": "unlock_drone", "description": "PLC nhả kẹp giải phóng Drone", "status": "waiting"},
            ]
        }
        uav_miss = {
            "drone_id": drone_id,
            "status": "in_progress",
            "current_step": "takeoff_from_home",
            "steps": [
                {"step": 1, "action": "takeoff_from_home", "start_location": "HOME", "target_altitude": 20.0, "description": "Cất cánh từ Vị trí HOME Pad", "status": "in_progress"},
                {"step": 2, "action": "goto_pickup", "description": "Bay từ HOME tới Điểm lấy hàng của Khách", "status": "waiting"},
                {"step": 3, "action": "precision_landing_pickup", "description": "Hạ cánh chính xác tại điểm hẹn lấy hàng", "status": "waiting"},
                {"step": 4, "action": "wait_pickup_confirm", "description": "Chờ Khách nạp hàng & nhấn Xác nhận", "status": "waiting"},
                {"step": 5, "action": "return_to_warehouse", "description": "Chở hàng bay quay trở về Trạm Kho HOME", "status": "waiting"},
                {"step": 6, "action": "precision_landing_warehouse_pad", "description": "Hạ cánh chính xác xuống Pad Trạm Kho HOME", "status": "waiting"},
            ]
        }
        return station_proc, uav_miss

    def _build_delivery_structures(self, drone_id: str, product_id: str, target_slot: Optional[str] = "A1") -> tuple[dict, dict]:
        station_proc = {
            "station_id": "STATION_WH_001",
            "status": "in_progress",
            "current_step": "plc_lock_drone",
            "steps": [
                {"step": 1, "device": "PLC", "action": "lock_drone", "description": "PLC Khóa kẹp cố định chân Drone trên Pad", "status": "waiting"},
                {"step": 2, "device": "ROBOT", "action": "pick_from_storage", "target_slot": target_slot or "A1", "description": f"Robot gắp sản phẩm từ ô kho {target_slot or 'A1'}", "status": "waiting"},
                {"step": 3, "device": "CAMERA", "action": "scan_qr_code", "description": f"Camera quét & xác nhận mã QR sản phẩm {product_id}", "status": "waiting"},
                {"step": 4, "device": "PLC", "action": "z_axis_up", "description": "PLC nâng trục Z bàn nâng lên đỉnh (Safety Interlock)", "status": "waiting"},
                {"step": 5, "device": "ROBOT", "action": "place_onto_uav", "description": "Robot đặt sản phẩm vào gá mang của Drone", "status": "waiting"},
                {"step": 6, "device": "PLC", "action": "z_axis_down", "description": "PLC hạ trục Z bàn nâng về vị trí an toàn", "status": "waiting"},
                {"step": 7, "device": "PLC", "action": "unlock_drone", "description": "PLC mở khóa kẹp giải phóng Drone", "status": "waiting"},
            ]
        }
        uav_miss = {
            "drone_id": drone_id,
            "status": "waiting",
            "current_step": "waiting_station_complete",
            "steps": [
                {"step": 1, "action": "takeoff_from_home", "start_location": "HOME", "target_altitude": 15.0, "description": "Drone cất cánh từ Vị trí HOME Pad", "status": "waiting"},
                {"step": 2, "action": "goto_delivery", "description": "Bay chuyển tiếp từ Home tới Tọa độ giao hàng Khách", "status": "waiting"},
                {"step": 3, "action": "descend_and_search_aruco", "description": "Hạ độ cao & Quét ArUco Marker điểm giao", "status": "waiting"},
                {"step": 4, "action": "precision_landing", "description": "Hạ cánh chính xác điểm giao hàng", "status": "waiting"},
                {"step": 5, "action": "wait_customer_confirm", "description": "Chờ khách nhận hàng & nhấn Xác nhận", "status": "waiting"},
                {"step": 6, "action": "return_home", "description": "Cất cánh bay trở về Vị trí HOME (RTL) & Hạ cánh", "status": "waiting"},
            ]
        }
        return station_proc, uav_miss

    def _update_step(self, process_dict: dict, step_idx: int, status: str) -> None:
        if process_dict and "steps" in process_dict and 0 <= step_idx < len(process_dict["steps"]):
            process_dict["steps"][step_idx]["status"] = status
            if status == "in_progress":
                process_dict["current_step"] = process_dict["steps"][step_idx].get("action", "")

    async def execute_drone_pickup(
        self, drone_id: str, product_id: str, location_type: str = "WAREHOUSE_PAD"
    ) -> IntralogisticsMissionRecord:
        """Flow Nhập Kho (DRONE_PICKUP) — Safety Interlocked Sequential Handshake."""
        self.qr_svc.stop_camera_scanner()

        station_proc, uav_miss = self._build_pickup_structures(drone_id, product_id)

        mission = IntralogisticsMissionRecord(
            mission_type="DRONE_PICKUP",
            drone_id=drone_id,
            product_id=product_id,
            state="STARTED",
            step_details="1. UAV arrived on pad. Camera OFF.",
            station_process_json=json.dumps(station_proc),
            uav_mission_json=json.dumps(uav_miss),
            created_at=datetime.utcnow(),
        )
        self.session.add(mission)
        await self.session.commit()
        await self.session.refresh(mission)

        # Safety Check
        eligible, reason = await self.validate_docking_eligibility(location_type)
        if not eligible:
            mission.state = "REJECTED_LOCATION"
            mission.step_details = f"🛑 TỪ CHỐI THỰC THI: {reason}"
            await self.log_event("SERVER", f"Mission #{mission.id} REJECTED: {reason}", log_type="ERROR_LOG")
            await self.session.commit()
            return mission

        await self.log_event("SERVER", f"Started DRONE_PICKUP mission #{mission.id} for product {product_id}")

        # Step 1: PLC LOCK_DRONE
        self._update_step(station_proc, 0, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        plc_res = await self.plc_mgr.execute_command(PLCCommand.LOCK_DRONE)
        if plc_res.plc_error:
            self._update_step(station_proc, 0, "failed")
            mission.station_process_json = json.dumps(station_proc)
            return await self._abort_mission(mission, "Step 1: PLC LOCK_DRONE failed or E-Stop triggered!")

        self._update_step(station_proc, 0, "completed")
        mission.state = "DOCK_LOCKED"
        mission.step_details = "2. PLC đã khóa cố định Drone trên pad (PLC_LOCK_DONE)."
        mission.station_process_json = json.dumps(station_proc)
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

        # Step 3: PLC Z_UP
        self._update_step(station_proc, 1, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        plc_res = await self.plc_mgr.execute_command(PLCCommand.Z_UP)
        if plc_res.plc_error or plc_res.z_axis != "UP":
            self._update_step(station_proc, 1, "failed")
            mission.station_process_json = json.dumps(station_proc)
            return await self._abort_mission(mission, "Step 3: PLC Z_UP failed! Trục Z chưa nâng.")

        self._update_step(station_proc, 1, "completed")
        mission.step_details = "4. PLC đã nâng trục Z lên vị trí trên (PLC_Z_UP_DONE)."
        mission.station_process_json = json.dumps(station_proc)
        await self.log_event("PLC", "Z_UP completed (PLC_Z_UP_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 4: ROBOT PICK_PRODUCT from UAV
        self._update_step(station_proc, 3, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        robot_res = await self.robot_mgr.execute_command(RobotCommand.PICK_PRODUCT)
        if robot_res.state == "ERROR":
            self._update_step(station_proc, 3, "failed")
            mission.station_process_json = json.dumps(station_proc)
            return await self._abort_mission(mission, "Step 4: Robot PICK_PRODUCT from UAV failed!")

        self._update_step(station_proc, 3, "completed")
        mission.state = "ROBOT_PICKING"
        mission.step_details = f"5. Robot đã gắp sản phẩm {product_id} từ UAV (ROBOT_DONE)."
        mission.station_process_json = json.dumps(station_proc)
        await self.log_event("ROBOT", f"Picked product {product_id} from UAV (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 5: ROBOT MOVE_HOME
        robot_res = await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        if robot_res.state == "ERROR":
            return await self._abort_mission(mission, "Step 5: Robot MOVE_HOME failed while carrying product!")

        mission.step_details = f"6. Robot mang {product_id} rút về vị trí HOME an toàn (ROBOT_DONE)."
        await self.log_event("ROBOT", f"Robot carrying {product_id} returned to HOME (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 6: PLC Z_DOWN
        self._update_step(station_proc, 5, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        plc_res = await self.plc_mgr.execute_command(PLCCommand.Z_DOWN)
        if plc_res.plc_error:
            self._update_step(station_proc, 5, "failed")
            mission.station_process_json = json.dumps(station_proc)
            return await self._abort_mission(mission, "Step 6: PLC Z_DOWN failed!")

        self._update_step(station_proc, 5, "completed")
        mission.step_details = "7. PLC đã hạ trục Z xuống vị trí dưới (PLC_Z_DOWN_DONE)."
        mission.station_process_json = json.dumps(station_proc)
        await self.log_event("PLC", "Z_DOWN completed (PLC_Z_DOWN_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 7: Camera ON -> QR Scan -> Find available storage slot
        self._update_step(station_proc, 2, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        self.qr_svc.start_camera_scanner()
        await self.qr_svc.notify_status_ws()
        await self.log_event("CAMERA", "Backend Camera TURNED ON to scan product QR code")
        mission.step_details = "8. Camera ON -> Đang quét mã QR sản phẩm."
        await self.session.commit()
        await self._notify_mission_progress(mission)
        await asyncio.sleep(1.5)

        scan_res = await self.qr_svc.process_qr_code(product_id, source="FSM_PICKUP_SCAN")
        free_slot = await self.inventory_mgr.find_available_slot()

        if free_slot or scan_res.get("slot_name"):
            target_slot = scan_res.get("slot_name") or (free_slot.slot_name if free_slot else "A1")
            mission.target_slot = target_slot
            self._update_step(station_proc, 2, "completed")

            # Step 8: ROBOT STORE
            self._update_step(station_proc, 4, "in_progress")
            if "steps" in station_proc and len(station_proc["steps"]) > 4:
                station_proc["steps"][4]["target_slot"] = target_slot
            mission.station_process_json = json.dumps(station_proc)

            robot_res = await self.robot_mgr.execute_command(RobotCommand.STORE, slot=target_slot)
            if robot_res.state == "ERROR":
                self._update_step(station_proc, 4, "failed")
                mission.station_process_json = json.dumps(station_proc)
                self.qr_svc.stop_camera_scanner()
                await self.qr_svc.notify_status_ws()
                return await self._abort_mission(mission, f"Step 8: Robot STORE into slot {target_slot} failed!")

            self._update_step(station_proc, 4, "completed")
            await self.inventory_mgr.update_slot(
                slot_name=target_slot,
                status=StorageSlotStatus.OCCUPIED,
                product_id=product_id,
                qr_code=product_id,
            )
            mission.state = "STORAGE_PLACED"
            mission.step_details = f"9. Robot đã cất sản phẩm vào ô {target_slot} (ROBOT_DONE)."
            mission.station_process_json = json.dumps(station_proc)
            await self.log_event("ROBOT", f"Stored product into slot {target_slot} (ROBOT_DONE)")
            await self.session.commit()
            await self._notify_mission_progress(mission)

            # Step 9: Camera OFF
            self.qr_svc.stop_camera_scanner()
            await self.qr_svc.notify_status_ws()
            await self.log_event("CAMERA", "Backend Camera TURNED OFF after placement.")

            # Step 10: PLC UNLOCK_DRONE -> Complete
            self._update_step(station_proc, 6, "in_progress")
            mission.station_process_json = json.dumps(station_proc)
            plc_res = await self.plc_mgr.execute_command(PLCCommand.UNLOCK_DRONE)
            if plc_res.plc_error:
                self._update_step(station_proc, 6, "failed")
                mission.station_process_json = json.dumps(station_proc)
                return await self._abort_mission(mission, "Step 10: PLC UNLOCK_DRONE failed!")

            self._update_step(station_proc, 6, "completed")
            station_proc["status"] = "completed"
            uav_miss["status"] = "completed"
            mission.state = "COMPLETED"
            mission.step_details = "10. PLC đã mở khóa Drone. Nhiệm vụ Nhập Kho HOÀN THÀNH!"
            mission.station_process_json = json.dumps(station_proc)
            mission.uav_mission_json = json.dumps(uav_miss)

            await self.log_event("SERVER", f"DRONE_PICKUP Mission #{mission.id} COMPLETED")
            await self.session.commit()
            await self._notify_mission_progress(mission)

            # Update linked delivery request if any & auto dispatch next
            await self._complete_and_auto_dispatch(mission)
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
        """Flow Xuất Kho (DRONE_DELIVERY) — Safety Interlocked Sequential Handshake."""
        self.qr_svc.stop_camera_scanner()

        slot_record = await self.inventory_mgr.find_slot_by_product_id(product_id)
        target_slot = slot_record.slot_name if slot_record else "A1"

        station_proc, uav_miss = self._build_delivery_structures(drone_id, product_id, target_slot)

        mission = IntralogisticsMissionRecord(
            mission_type="DRONE_DELIVERY",
            drone_id=drone_id,
            product_id=product_id,
            target_slot=target_slot,
            state="STARTED",
            step_details="1. Delivery request started. Camera OFF.",
            station_process_json=json.dumps(station_proc),
            uav_mission_json=json.dumps(uav_miss),
            created_at=datetime.utcnow(),
        )
        self.session.add(mission)
        await self.session.commit()
        await self.session.refresh(mission)

        # Dual Safety Check
        eligible, reason = await self.validate_docking_eligibility(location_type)
        if not eligible:
            mission.state = "REJECTED_LOCATION"
            mission.step_details = f"🛑 TỪ CHỐI THỰC THI: {reason}"
            await self.log_event("SERVER", f"Mission #{mission.id} REJECTED: {reason}", log_type="ERROR_LOG")
            await self.session.commit()
            return mission

        await self.log_event("SERVER", f"Started DRONE_DELIVERY mission #{mission.id} for product {product_id}")

        # Step 1: PLC LOCK_DRONE
        self._update_step(station_proc, 0, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        plc_res = await self.plc_mgr.execute_command(PLCCommand.LOCK_DRONE)
        if plc_res.plc_error:
            self._update_step(station_proc, 0, "failed")
            mission.station_process_json = json.dumps(station_proc)
            return await self._abort_mission(mission, "Step 1: PLC LOCK_DRONE failed!")

        self._update_step(station_proc, 0, "completed")
        mission.state = "DOCK_LOCKED"
        mission.step_details = "2. PLC đã khóa cố định Drone trên pad (PLC_LOCK_DONE)."
        mission.station_process_json = json.dumps(station_proc)
        await self.log_event("PLC", "Drone locked on pad (PLC_LOCK_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 2: Find product location & Robot PICK
        if not slot_record:
            mission.state = "ERROR_PRODUCT_NOT_FOUND"
            mission.step_details = f"Product {product_id} not found in warehouse storage slots!"
            await self.log_event("SERVER", f"Product {product_id} not found in inventory", log_type="ERROR_LOG")
            await self.session.commit()
            await self._notify_mission_progress(mission)
            return mission

        self._update_step(station_proc, 1, "in_progress")
        mission.station_process_json = json.dumps(station_proc)

        robot_res = await self.robot_mgr.execute_command(RobotCommand.PICK, slot=target_slot)
        if robot_res.state == "ERROR":
            self._update_step(station_proc, 1, "failed")
            mission.station_process_json = json.dumps(station_proc)
            return await self._abort_mission(mission, f"Step 3: Robot PICK from slot {target_slot} failed!")

        self._update_step(station_proc, 1, "completed")
        await self.inventory_mgr.update_slot(slot_name=target_slot, status=StorageSlotStatus.EMPTY)
        mission.state = "ROBOT_PICKING"
        mission.step_details = f"3. Robot đã lấy sản phẩm {product_id} từ ô {target_slot} (ROBOT_DONE)."
        mission.station_process_json = json.dumps(station_proc)
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
        self._update_step(station_proc, 2, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        self.qr_svc.start_camera_scanner()
        await self.qr_svc.notify_status_ws()
        await self.log_event("CAMERA", f"Backend Camera TURNED ON -> Verified robot carrying product {product_id}")
        mission.step_details = f"5. Camera ON -> Đã xác nhận robot đang mang sản phẩm {product_id}."
        await self.session.commit()
        await self._notify_mission_progress(mission)
        await asyncio.sleep(1.5)
        self._update_step(station_proc, 2, "completed")

        # Step 6: PLC Z_UP
        self._update_step(station_proc, 3, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        plc_res = await self.plc_mgr.execute_command(PLCCommand.Z_UP)
        if plc_res.plc_error or plc_res.z_axis != "UP":
            self._update_step(station_proc, 3, "failed")
            self.qr_svc.stop_camera_scanner()
            await self.qr_svc.notify_status_ws()
            mission.station_process_json = json.dumps(station_proc)
            return await self._abort_mission(mission, "Step 6: PLC Z_UP failed! Trục Z chưa nâng.")

        self._update_step(station_proc, 3, "completed")
        mission.step_details = "6. PLC đã nâng trục Z lên (PLC_Z_UP_DONE)."
        mission.station_process_json = json.dumps(station_proc)
        await self.log_event("PLC", "Z_UP completed (PLC_Z_UP_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 7: ROBOT PLACE_PRODUCT onto UAV
        self._update_step(station_proc, 4, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        robot_res = await self.robot_mgr.execute_command(RobotCommand.PLACE_PRODUCT)
        if robot_res.state == "ERROR":
            self._update_step(station_proc, 4, "failed")
            self.qr_svc.stop_camera_scanner()
            await self.qr_svc.notify_status_ws()
            mission.station_process_json = json.dumps(station_proc)
            return await self._abort_mission(mission, "Step 7: Robot PLACE_PRODUCT onto UAV failed!")

        self._update_step(station_proc, 4, "completed")
        mission.step_details = f"7. Robot đã đặt sản phẩm {product_id} lên UAV (ROBOT_DONE)."
        mission.station_process_json = json.dumps(station_proc)
        await self.log_event("ROBOT", f"Placed product {product_id} onto UAV (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 8: ROBOT MOVE_HOME
        robot_res = await self.robot_mgr.execute_command(RobotCommand.MOVE_HOME)
        if robot_res.state == "ERROR":
            self.qr_svc.stop_camera_scanner()
            await self.qr_svc.notify_status_ws()
            return await self._abort_mission(mission, "Step 8: Robot MOVE_HOME failed after placing product!")

        mission.step_details = "8. Robot đã rút về vị trí HOME an toàn (ROBOT_DONE)."
        await self.log_event("ROBOT", "Robot returned to HOME after placing product (ROBOT_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 9: Camera OFF
        self.qr_svc.stop_camera_scanner()
        await self.qr_svc.notify_status_ws()
        await self.log_event("CAMERA", "Backend Camera TURNED OFF after placement.")

        # Step 10: PLC Z_DOWN
        self._update_step(station_proc, 5, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        plc_res = await self.plc_mgr.execute_command(PLCCommand.Z_DOWN)
        if plc_res.plc_error:
            self._update_step(station_proc, 5, "failed")
            mission.station_process_json = json.dumps(station_proc)
            return await self._abort_mission(mission, "Step 10: PLC Z_DOWN failed!")

        self._update_step(station_proc, 5, "completed")
        mission.state = "STORAGE_PLACED"
        mission.step_details = "9. PLC đã hạ trục Z xuống (PLC_Z_DOWN_DONE)."
        mission.station_process_json = json.dumps(station_proc)
        await self.log_event("PLC", "Z_DOWN completed (PLC_Z_DOWN_DONE)")
        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Step 11: PLC UNLOCK_DRONE -> Complete
        self._update_step(station_proc, 6, "in_progress")
        mission.station_process_json = json.dumps(station_proc)
        plc_res = await self.plc_mgr.execute_command(PLCCommand.UNLOCK_DRONE)
        if plc_res.plc_error:
            self._update_step(station_proc, 6, "failed")
            mission.station_process_json = json.dumps(station_proc)
            return await self._abort_mission(mission, "Step 11: PLC UNLOCK_DRONE failed!")

        self._update_step(station_proc, 6, "completed")
        station_proc["status"] = "completed"
        uav_miss["status"] = "completed"

        mission.state = "COMPLETED"
        mission.step_details = "10-11. PLC đã mở khóa Drone. Camera OFF. Nhiệm vụ Xuất Kho HOÀN THÀNH!"
        mission.station_process_json = json.dumps(station_proc)
        mission.uav_mission_json = json.dumps(uav_miss)
        await self.log_event("SERVER", f"DRONE_DELIVERY Mission #{mission.id} COMPLETED")

        await self.session.commit()
        await self._notify_mission_progress(mission)

        # Update linked delivery request if any & auto dispatch next
        await self._complete_and_auto_dispatch(mission)

        await self.session.refresh(mission)
        return mission

    async def _complete_and_auto_dispatch(self, mission: IntralogisticsMissionRecord) -> None:
        """Helper to update DeliveryRequest status and auto dispatch next pending order."""
        try:
            # Update linked delivery request if matching mission_id exists
            stmt = select(DeliveryRequestRecord).where(DeliveryRequestRecord.mission_id == mission.id)
            res = await self.session.execute(stmt)
            linked_req = res.scalars().first()
            if linked_req:
                linked_req.status = "DELIVERED"
                await self.session.commit()
                await system_ws_manager.broadcast("DELIVERY_UPDATE", {"id": linked_req.id, "status": "DELIVERED"})

            # Auto-Dispatch next pending mission in background (with fresh session)
            asyncio.create_task(MissionManager._auto_dispatch_with_new_session())
        except Exception as e:
            logger.error("Error in _complete_and_auto_dispatch: %s", e)

    @staticmethod
    async def _auto_dispatch_with_new_session() -> None:
        """Wrapper that creates a fresh DB session for auto-dispatching the next order."""
        from app.database.repository import async_session as session_factory
        await asyncio.sleep(1.0)  # Small delay to let current mission fully commit
        try:
            async with session_factory() as new_session:
                mgr = MissionManager(new_session)
                await mgr.auto_dispatch_next_mission()
        except Exception as err:
            logger.error("Error in _auto_dispatch_with_new_session: %s", err)

    async def auto_dispatch_next_mission(self) -> Optional[IntralogisticsMissionRecord]:
        """Auto-Queue Dispatcher: Checks for next APPROVED or PENDING delivery request in DB and triggers it automatically."""
        try:
            active = await self.get_active_mission()
            if active:
                logger.info("[Auto-Dispatcher] Mission #%d is currently active (state %s). Skipping.", active.id, active.state)
                return None

            # Strict Single Mission Guard: Check if ANY DeliveryRequest is currently FLYING
            stmt_flying = select(DeliveryRequestRecord).where(DeliveryRequestRecord.status == "FLYING")
            res_flying = await self.session.execute(stmt_flying)
            existing_flying = res_flying.scalars().first()
            if existing_flying:
                logger.info("[Auto-Dispatcher] DeliveryRequest #%d is currently FLYING. Only 1 order allowed at a time. Skipping.", existing_flying.id)
                return None

            stmt = select(DeliveryRequestRecord).where(
                DeliveryRequestRecord.status.in_(["APPROVED", "PENDING"])
            ).order_by(DeliveryRequestRecord.id.asc())
            res = await self.session.execute(stmt)
            pending_req = res.scalars().first()

            if not pending_req:
                logger.info("[Auto-Dispatcher] No pending orders in queue.")
                return None

            logger.info("[Auto-Dispatcher] Auto-triggering delivery request #%d (Type: %s)", pending_req.id, pending_req.delivery_type)
            pending_req.status = "FLYING"
            await self.session.commit()
            await system_ws_manager.broadcast("DELIVERY_UPDATE", {"id": pending_req.id, "status": "FLYING"})
            await system_ws_manager.broadcast("delivery_requests_update", {})

            m_type = "DRONE_DELIVERY" if pending_req.delivery_type == "RECEIVE_FROM_WAREHOUSE" else "DRONE_PICKUP"

            if m_type == "DRONE_DELIVERY":
                slot_record = await self.inventory_mgr.find_occupied_slot()
                product_id = slot_record.product_id if (slot_record and slot_record.product_id) else f"ITEM-OUT-{pending_req.id}"
                mission = await self.execute_drone_delivery(drone_id="UAV01", product_id=product_id)
            else:
                product_id = f"ITEM-IN-{pending_req.id}"
                mission = await self.execute_drone_pickup(drone_id="UAV01", product_id=product_id)

            pending_req.mission_id = mission.id

            # If mission failed/rejected immediately upon creation, sync order status away from FLYING!
            if mission.state in ("FAILED", "REJECTED_LOCATION", "ERROR_NO_FREE_SLOT"):
                pending_req.status = "FAILED"
                await system_ws_manager.broadcast("DELIVERY_UPDATE", {"id": pending_req.id, "status": "FAILED"})
                await system_ws_manager.broadcast("delivery_requests_update", {})

            await self.session.commit()
            return mission
        except Exception as err:
            logger.error("Error in auto_dispatch_next_mission: %s", err)
        return None

    async def _abort_mission(self, mission: IntralogisticsMissionRecord, reason: str) -> IntralogisticsMissionRecord:
        """Helper to safely abort mission on hardware failure or timeout."""
        logger.error("🛑 ABORTING MISSION #%d: %s", mission.id, reason)
        mission.state = "FAILED"
        mission.step_details = f"🛑 DỪNG KHẨN CẤP: {reason}"
        await self.log_event("SERVER", f"Mission #{mission.id} ABORTED: {reason}", log_type="ERROR_LOG")

        # Sync linked DeliveryRequest status from FLYING -> FAILED
        stmt = select(DeliveryRequestRecord).where(
            (DeliveryRequestRecord.mission_id == mission.id) | (DeliveryRequestRecord.status == "FLYING")
        )
        res = await self.session.execute(stmt)
        reqs = res.scalars().all()
        for req in reqs:
            req.status = "FAILED"

        await self.session.commit()
        await self._notify_mission_progress(mission)
        await system_ws_manager.broadcast("delivery_requests_update", {})
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
        """Find the currently active (in-progress) mission, excluding all terminal/blocked states."""
        terminal_states = [
            "COMPLETED", "FAILED", "CANCELLED",
            "ERROR_NO_FREE_SLOT", "ERROR_PRODUCT_NOT_FOUND",
            "REJECTED_LOCATION",
        ]
        stmt = select(IntralogisticsMissionRecord).where(
            IntralogisticsMissionRecord.state.notin_(terminal_states)
        ).order_by(IntralogisticsMissionRecord.id.desc())
        res = await self.session.execute(stmt)
        active = res.scalars().first()

        # Safety Timeout Check: If active mission hasn't updated in > 180 seconds, auto-abort it
        if active:
            now = datetime.utcnow()
            updated_at = active.updated_at or active.created_at
            if updated_at and (now - updated_at).total_seconds() > 180:
                logger.warning("Active mission #%d timed out (>180s in state %s). Auto-aborting.", active.id, active.state)
                await self._abort_mission(active, "Nhiệm vụ quá thời gian thực thi quy định (>180s)")
                return None

        return active


