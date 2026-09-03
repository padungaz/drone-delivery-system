import asyncio
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import IntralogisticsMissionRecord, SystemLogRecord, DeliveryRequestRecord
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.services.inventory_manager import InventoryManager
from app.services.station_service import StationService
from app.services.mission_queue_manager import MissionQueueManager
from app.services.fleet_manager import fleet_manager
from app.services.system_mode_manager import system_mode_manager
from app.services.device_lock_manager import device_lock_manager
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)


class MissionManager:
    """Master Intralogistics Mission Orchestrator — Layer 2: Decoupled Mission Lifecycle.

    Architecture: 4-Layer Decoupled Design
    ======================================
    1. Customer Order Layer (DeliveryRequest)  : Who, What, Pickup/Dropoff, Status
    2. Mission Orchestration Layer (Mission)  : High-level lifecycle & phases
    3. Station Task Service (StationService)  : Docking Station hardware execution (LOAD/UNLOAD)
    4. Device Managers Layer (PLC/Robot/UAV)  : Device drivers & Socket/Snap7 communication

    The Mission layer coordinates high-level phases:
      - WAITING → STATION_PROCESSING → DRONE_EN_ROUTE → COMPLETED
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.plc_mgr = PLCManager.get_instance()
        self.robot_mgr = RobotManager.get_instance()
        self.inventory_mgr = InventoryManager(session)
        self.station_svc = StationService(session)

    def _serialize_mission(self, mission: IntralogisticsMissionRecord) -> dict:
        return {
            "id": mission.id,
            "order_id": mission.order_id,
            "mission_type": mission.mission_type,
            "drone_id": mission.drone_id,
            "product_id": mission.product_id,
            "target_slot": mission.target_slot,
            "status": mission.status or mission.state or "QUEUED",
            "current_phase": mission.current_phase or "WAITING",
            "state": mission.status or mission.state or "QUEUED",  # Backward compatibility
            "step_details": mission.step_details,
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
                "status": m_dict["status"],
                "current_phase": m_dict["current_phase"],
                "state": m_dict["status"],
                "step_details": mission.step_details,
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

    async def execute_drone_pickup(
        self, drone_id: str, product_id: str, location_type: str = "WAREHOUSE_PAD", order_id: Optional[int] = None, auto_run: bool = True
    ) -> IntralogisticsMissionRecord:
        """Flow Nhập Kho (DRONE_PICKUP) — Layer 2 Mission Orchestration & Queue Manager."""
        active = await self.get_active_mission()
        should_run_now = auto_run and (active is None) and system_mode_manager.can_auto_dispatch()

        free_slot_rec = await self.inventory_mgr.find_available_slot()
        target_slot = free_slot_rec.slot_name if free_slot_rec else "A1"

        status_init = "RUNNING" if should_run_now else "WAITING"
        phase_init = "STATION_PROCESSING" if should_run_now else "WAITING"

        # Determine/assign available UAV from Fleet
        assigned_uav_id = drone_id
        if not assigned_uav_id or assigned_uav_id in ("UAV01", "drone-01"):
            ready_uavs = [u for u in fleet_manager.fleet.values() if u.state == "READY"]
            if ready_uavs:
                assigned_uav_id = ready_uavs[0].drone_id

        mission = IntralogisticsMissionRecord(
            order_id=order_id,
            mission_type="DRONE_PICKUP",
            drone_id=assigned_uav_id,
            product_id=product_id,
            target_slot=target_slot,
            status=status_init,
            current_phase=phase_init,
            state=status_init,
            step_details="🚀 Đang chạy Nhiệm vụ Nhập kho (DRONE_PICKUP)..." if should_run_now else "Nhiệm vụ ở Hàng chờ (WAITING FIFO).",
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow() if should_run_now else None,
        )
        self.session.add(mission)
        await self.session.commit()
        await self.session.refresh(mission)

        # Notify fleet assignment
        fleet_manager.assign_available_uav(mission.id, "DRONE_PICKUP")
        await fleet_manager.broadcast_fleet_state()

        await self.log_event("SERVER", f"Created DRONE_PICKUP mission #{mission.id} for product {product_id} with {assigned_uav_id} (Status: {status_init})")
        
        q_mgr = MissionQueueManager(self.session)
        await q_mgr.broadcast_queue_state()

        if should_run_now:
            device_lock_manager.lock_station(mission.id, reason=f"Executing DRONE_PICKUP Mission #{mission.id}")
            await system_ws_manager.broadcast("MISSION_STARTED", self._serialize_mission(mission))
            asyncio.create_task(MissionManager._run_pickup_task_with_new_session(mission.id))

        return mission

    async def execute_drone_delivery(
        self, drone_id: str, product_id: str, location_type: str = "WAREHOUSE_PAD", order_id: Optional[int] = None, auto_run: bool = True
    ) -> IntralogisticsMissionRecord:
        """Flow Xuất Kho (DRONE_DELIVERY) — Layer 2 Mission Orchestration & Queue Manager."""
        active = await self.get_active_mission()
        should_run_now = auto_run and (active is None) and system_mode_manager.can_auto_dispatch()

        slot_record = await self.inventory_mgr.find_slot_by_product_id(product_id)
        if not slot_record:
            slot_record = await self.inventory_mgr.find_occupied_slot()
        target_slot = slot_record.slot_name if slot_record else "A1"

        status_init = "RUNNING" if should_run_now else "WAITING"
        phase_init = "STATION_PROCESSING" if should_run_now else "WAITING"

        # Determine/assign available UAV from Fleet
        assigned_uav_id = drone_id
        if not assigned_uav_id or assigned_uav_id in ("UAV01", "drone-01"):
            ready_uavs = [u for u in fleet_manager.fleet.values() if u.state == "READY"]
            if ready_uavs:
                assigned_uav_id = ready_uavs[0].drone_id

        mission = IntralogisticsMissionRecord(
            order_id=order_id,
            mission_type="DRONE_DELIVERY",
            drone_id=assigned_uav_id,
            product_id=product_id,
            target_slot=target_slot,
            status=status_init,
            current_phase=phase_init,
            state=status_init,
            step_details="🚀 Đang chạy Nhiệm vụ Xuất kho (DRONE_DELIVERY)..." if should_run_now else "Nhiệm vụ ở Hàng chờ (WAITING FIFO).",
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow() if should_run_now else None,
        )
        self.session.add(mission)
        await self.session.commit()
        await self.session.refresh(mission)

        # Notify fleet assignment
        fleet_manager.assign_available_uav(mission.id, "DRONE_DELIVERY")
        await fleet_manager.broadcast_fleet_state()

        await self.log_event("SERVER", f"Created DRONE_DELIVERY mission #{mission.id} for product {product_id} with {assigned_uav_id} (Status: {status_init})")

        q_mgr = MissionQueueManager(self.session)
        await q_mgr.broadcast_queue_state()

        if should_run_now:
            device_lock_manager.lock_station(mission.id, reason=f"Executing DRONE_DELIVERY Mission #{mission.id}")
            await system_ws_manager.broadcast("MISSION_STARTED", self._serialize_mission(mission))
            asyncio.create_task(MissionManager._run_delivery_task_with_new_session(mission.id))

        return mission

    @staticmethod
    async def _run_delivery_task_with_new_session(mission_id: int) -> None:
        from app.database.repository import async_session as session_factory
        try:
            async with session_factory() as new_session:
                mgr = MissionManager(new_session)
                await mgr.run_automated_delivery_sequence(mission_id)
        except Exception as err:
            logger.error("Error in _run_delivery_task_with_new_session for mission #%d: %s", mission_id, err)

    @staticmethod
    async def _run_pickup_task_with_new_session(mission_id: int) -> None:
        from app.database.repository import async_session as session_factory
        try:
            async with session_factory() as new_session:
                mgr = MissionManager(new_session)
                await mgr.run_automated_pickup_sequence(mission_id)
        except Exception as err:
            logger.error("Error in _run_pickup_task_with_new_session for mission #%d: %s", mission_id, err)

    async def run_automated_delivery_sequence(self, mission_id: int) -> None:
        """Automated Phase Orchestration for DRONE_DELIVERY (Xuất kho giao hàng)."""
        mission = await self.session.get(IntralogisticsMissionRecord, mission_id)
        if not mission:
            return

        try:
            device_lock_manager.lock_station(mission_id, reason=f"Executing DRONE_DELIVERY Mission #{mission.id}")
            target_slot = mission.target_slot or "A1"

            # Phase 1: STATION_PROCESSING (Station Hardware Sequence)
            mission.status = "RUNNING"
            mission.state = "RUNNING"
            mission.current_phase = "STATION_PROCESSING"
            mission.step_details = f"⚙️ Station Controller đang thực thi xuất hàng từ ô kho {target_slot}..."
            await self.session.commit()
            await self._notify_mission_progress(mission)
            await fleet_manager.signal_drone_loading(mission.drone_id)

            success = await self.station_svc.execute_load_product(target_slot, mission.product_id, self.session)
            if not success:
                raise Exception(f"Station Controller LOAD_PRODUCT operation failed for slot {target_slot}")

            # Station loading complete -> Release station lock
            device_lock_manager.unlock_station()
            await fleet_manager.signal_station_loaded(mission.drone_id)

            # Bỏ qua phần UAV: Không chờ bay hay điều hướng Drone
            # Đã giải phóng ô kho thành EMPTY và xác nhận DRONE_DETECT = 0 (Drone đã rời Pad N1) -> Hoàn tất đơn hàng và tự động chạy đơn tiếp theo
            mission.current_phase = "COMPLETED"
            mission.status = "COMPLETED"
            mission.state = "COMPLETED"
            mission.completed_at = datetime.utcnow()
            mission.step_details = f"✅ Ô {target_slot} đã EMPTY & Drone đã rời bãi N1 (DRONE_DETECT=0)! Đơn #{mission.id} hoàn thành -> Tự động chuyển đơn tiếp theo."
            await self.session.commit()
            await self.log_event("SERVER", f"Mission #{mission.id} (DRONE_DELIVERY) COMPLETED (DRONE_DETECT=0) -> Tự động chuyển đơn hàng tiếp theo")
            await system_ws_manager.broadcast("MISSION_COMPLETED", self._serialize_mission(mission))
            await self._complete_and_auto_dispatch(mission)

        except Exception as err:
            logger.error("Error in run_automated_delivery_sequence for mission #%d: %s", mission_id, err)
            await self._abort_mission(mission, str(err))

    async def run_automated_pickup_sequence(self, mission_id: int) -> None:
        """Automated Phase Orchestration for DRONE_PICKUP (Nhập kho nhận hàng)."""
        mission = await self.session.get(IntralogisticsMissionRecord, mission_id)
        if not mission:
            return

        try:
            # Phase 1: DRONE_EN_ROUTE
            mission.status = "RUNNING"
            mission.state = "RUNNING"
            mission.current_phase = "DRONE_EN_ROUTE"
            mission.step_details = f"🚁 Drone {mission.drone_id} bay đến vị trí lấy hàng và về trạm N1..."
            await self.session.commit()
            await self._notify_mission_progress(mission)
            await self.log_event("UAV_FLIGHT", f"Drone {mission.drone_id} dispatched for customer pickup")

            await asyncio.sleep(1.0)

            # Signal PLC sensor & Fleet Arrival
            await fleet_manager.signal_drone_arrived(mission.drone_id)

            # Phase 2: STATION_PROCESSING
            device_lock_manager.lock_station(mission_id, reason=f"Executing DRONE_PICKUP Mission #{mission.id}")
            free_slot_rec = await self.inventory_mgr.find_available_slot()
            if not free_slot_rec:
                raise Exception("Kho hàng đã đầy! Không còn Ô kho trống (ERROR_NO_FREE_SLOT).")

            target_slot = free_slot_rec.slot_name
            mission.target_slot = target_slot
            mission.current_phase = "STATION_PROCESSING"
            mission.step_details = f"⚙️ Station Controller đang thực thi nhập hàng vào ô kho {target_slot}..."
            await self.session.commit()
            await self._notify_mission_progress(mission)
            await fleet_manager.signal_drone_loading(mission.drone_id)

            success = await self.station_svc.execute_unload_product(target_slot, mission.product_id, self.session)
            if not success:
                raise Exception(f"Station Controller UNLOAD_PRODUCT operation failed for slot {target_slot}")

            # Station unloaded -> Release station lock
            device_lock_manager.unlock_station()
            await fleet_manager.signal_station_unloaded(mission.drone_id)

            # Phase 3: COMPLETED
            mission.current_phase = "COMPLETED"
            mission.status = "COMPLETED"
            mission.state = "COMPLETED"
            mission.completed_at = datetime.utcnow()
            mission.step_details = f"✅ Nhiệm vụ Nhập Kho #{mission.id} cất sản phẩm {mission.product_id} vào ô {target_slot} HOÀN THÀNH!"
            await self.session.commit()
            await self.log_event("SERVER", f"Mission #{mission.id} (DRONE_PICKUP) COMPLETED")
            await system_ws_manager.broadcast("MISSION_COMPLETED", self._serialize_mission(mission))
            await self._complete_and_auto_dispatch(mission)

        except Exception as err:
            logger.error("Error in run_automated_pickup_sequence for mission #%d: %s", mission_id, err)
            await self._abort_mission(mission, str(err))

    async def _complete_and_auto_dispatch(self, mission: IntralogisticsMissionRecord) -> None:
        """Helper to update DeliveryRequest status, update Queue state and auto dispatch next waiting mission."""
        try:
            device_lock_manager.unlock_station()
            if mission.order_id:
                linked_req = await self.session.get(DeliveryRequestRecord, mission.order_id)
                if linked_req:
                    linked_req.status = "DELIVERED"
                    await self.session.commit()
                    await system_ws_manager.broadcast("DELIVERY_UPDATE", {"id": linked_req.id, "status": "DELIVERED"})

            q_mgr = MissionQueueManager(self.session)
            await q_mgr.broadcast_queue_state()

            # Auto-Dispatch next WAITING mission from FIFO Queue if AUTO mode
            if system_mode_manager.is_auto():
                asyncio.create_task(MissionManager._auto_dispatch_with_new_session())
        except Exception as e:
            logger.error("Error in _complete_and_auto_dispatch: %s", e)

    @staticmethod
    async def _auto_dispatch_with_new_session() -> None:
        from app.database.repository import async_session as session_factory
        await asyncio.sleep(0.5)
        try:
            async with session_factory() as new_session:
                mgr = MissionManager(new_session)
                await mgr.auto_dispatch_next_mission()
        except Exception as err:
            logger.error("Error in _auto_dispatch_with_new_session: %s", err)

    async def auto_dispatch_next_mission(self) -> Optional[IntralogisticsMissionRecord]:
        """FIFO Auto-Queue Dispatcher: Triggers next WAITING mission in queue."""
        try:
            if not system_mode_manager.is_auto() or system_mode_manager.is_staff_mode():
                logger.info("[Auto-Dispatcher] System is in MANUAL mode or Staff mode. Skipping auto-dispatch.")
                return None

            q_mgr = MissionQueueManager(self.session)
            active = await q_mgr.get_active_mission()
            if active:
                logger.info("[Auto-Dispatcher] Mission #%d is currently RUNNING. Skipping.", active.id)
                return None

            waiting_list = await q_mgr.get_waiting_queue()
            if not waiting_list:
                logger.info("[Auto-Dispatcher] Queue is empty. No waiting missions.")
                return None

            next_mission = waiting_list[0]
            logger.info("[Auto-Dispatcher] FIFO Dispatching next mission #%d (%s for product %s)", next_mission.id, next_mission.mission_type, next_mission.product_id)

            next_mission.status = "RUNNING"
            next_mission.state = "RUNNING"
            next_mission.current_phase = "STATION_PROCESSING" if next_mission.mission_type == "DRONE_DELIVERY" else "DRONE_EN_ROUTE"
            next_mission.started_at = datetime.utcnow()
            next_mission.step_details = f"🚀 Tự động thực thi Đơn hàng FIFO #{next_mission.id} ({next_mission.mission_type})..."
            await self.session.commit()

            device_lock_manager.lock_station(next_mission.id, reason=f"Auto-dispatching Mission #{next_mission.id}")
            await system_ws_manager.broadcast("MISSION_STARTED", self._serialize_mission(next_mission))
            await q_mgr.broadcast_queue_state()

            if next_mission.mission_type == "DRONE_DELIVERY":
                asyncio.create_task(MissionManager._run_delivery_task_with_new_session(next_mission.id))
            else:
                asyncio.create_task(MissionManager._run_pickup_task_with_new_session(next_mission.id))

            return next_mission
        except Exception as err:
            logger.error("Error in auto_dispatch_next_mission: %s", err)
        return None

    async def _abort_mission(self, mission: IntralogisticsMissionRecord, reason: str) -> IntralogisticsMissionRecord:
        """Safely abort mission on error or timeout, broadcast MISSION_FAILED, and STOP auto-dispatch for safety."""
        logger.error("🛑 ABORTING MISSION #%d: %s", mission.id, reason)
        device_lock_manager.unlock_station()

        mission.status = "FAILED"
        mission.state = "FAILED"
        mission.current_phase = "FAILED"
        mission.error_reason = reason
        mission.step_details = f"🛑 DỪNG LỖI: {reason}"
        await self.log_event("SERVER", f"Mission #{mission.id} FAILED: {reason}", log_type="ERROR_LOG")

        if mission.order_id:
            req = await self.session.get(DeliveryRequestRecord, mission.order_id)
            if req:
                req.status = "FAILED"

        await self.session.commit()
        await self._notify_mission_progress(mission)
        await system_ws_manager.broadcast("MISSION_FAILED", self._serialize_mission(mission))

        # Broadcast safety alert — DO NOT auto-dispatch next mission automatically on failure!
        await system_ws_manager.broadcast("SYSTEM_ALERT", {
            "level": "ERROR",
            "message": f"🛑 Nhiệm vụ #{mission.id} bị lỗi ({reason}). Hàng đợi tự động đã tạm dừng để đảm bảo an toàn. Vui lòng kiểm tra thiết bị trước khi tiếp tục!",
        })

        q_mgr = MissionQueueManager(self.session)
        await q_mgr.broadcast_queue_state()

        await self.session.refresh(mission)
        return mission

    async def pause_mission(self, mission_id: Optional[int] = None) -> Optional[IntralogisticsMissionRecord]:
        mission = await self.get_active_mission() if not mission_id else await self.session.get(IntralogisticsMissionRecord, mission_id)
        if mission and mission.status not in ("COMPLETED", "FAILED"):
            mission.status = "PAUSED"
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
            stmt = select(IntralogisticsMissionRecord).where(IntralogisticsMissionRecord.status == "PAUSED").order_by(IntralogisticsMissionRecord.id.desc())
            res = await self.session.execute(stmt)
            mission = res.scalars().first()

        if mission and mission.status == "PAUSED":
            mission.status = "RUNNING"
            mission.state = "RUNNING"
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
        """Fetch currently RUNNING mission, with timeout check."""
        stmt = select(IntralogisticsMissionRecord).where(
            IntralogisticsMissionRecord.status == "RUNNING"
        ).order_by(IntralogisticsMissionRecord.id.desc())
        res = await self.session.execute(stmt)
        active = res.scalars().first()

        if active:
            now = datetime.utcnow()
            updated_at = active.updated_at or active.started_at or active.created_at
            if updated_at and (now - updated_at).total_seconds() > 180:
                logger.warning("Active mission #%d timed out (>180s in phase %s). Auto-aborting.", active.id, active.current_phase)
                await self._abort_mission(active, "Nhiệm vụ quá thời gian thực thi quy định (>180s)")
                return None

        return active
