import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import get_session
from app.models.schemas import PLCCommand
from app.services.fleet_manager import fleet_manager
from app.services.system_mode_manager import system_mode_manager
from app.services.mission_manager import MissionManager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.websocket.manager import system_ws_manager

logger = logging.getLogger(__name__)

fleet_router = APIRouter(tags=["UAV Fleet & System Operations"])


class FlightModeRequest(BaseModel):
    mode: str  # "AUTO" | "MANUAL"


@fleet_router.get("/api/fleet/status")
@fleet_router.get("/api/fleet", include_in_schema=False)
async def get_fleet_status():
    """Returns status of all UAV units in the fleet."""
    return {
        "fleet": fleet_manager.get_all_uavs(),
        "total_uavs": len(fleet_manager.fleet),
    }


@fleet_router.post("/api/fleet/{drone_id}/signal/arrive")
async def signal_drone_arrived(drone_id: str):
    """Signal/Simulate that UAV has arrived and landed at Docking Pad N1."""
    try:
        uav = await fleet_manager.signal_drone_arrived(drone_id)
        return {
            "status": "SUCCESS",
            "message": f"UAV {drone_id} đã hạ cánh tại Bãi đáp Trạm N1 (PLC drone_detected = TRUE)",
            "uav": uav.model_dump(mode="json"),
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))


@fleet_router.post("/api/fleet/{drone_id}/signal/depart-home")
async def signal_drone_depart_home(drone_id: str):
    """Signal/Simulate that UAV has taken off to return home, clearing the dock pad."""
    try:
        uav = await fleet_manager.signal_drone_depart_home(drone_id)
        return {
            "status": "SUCCESS",
            "message": f"UAV {drone_id} đã cất cánh về Home. Bãi đáp N1 đã giải phóng.",
            "uav": uav.model_dump(mode="json"),
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))


@fleet_router.post("/api/fleet/{drone_id}/signal/depart-delivery")
async def signal_drone_depart_delivery(drone_id: str):
    """Signal/Simulate that UAV has taken off for customer delivery."""
    try:
        uav = await fleet_manager.signal_drone_depart_delivery(drone_id)
        return {
            "status": "SUCCESS",
            "message": f"UAV {drone_id} đã nhận hàng và cất cánh bay đi giao cho khách.",
            "uav": uav.model_dump(mode="json"),
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))


@fleet_router.post("/api/fleet/{drone_id}/mode")
async def set_drone_flight_mode(drone_id: str, req: FlightModeRequest):
    """Set flight mode for UAV (AUTO or MANUAL)."""
    try:
        uav = await fleet_manager.set_flight_mode(drone_id, req.mode)
        return {
            "status": "SUCCESS",
            "drone_id": drone_id,
            "flight_mode": uav.flight_mode,
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))


class SystemModeRequest(BaseModel):
    mode: str  # "AUTO" | "MANUAL"


@fleet_router.get("/api/system/mode")
async def get_system_mode():
    """Get current global system operation mode (AUTO or MANUAL)."""
    return system_mode_manager.get_status()


@fleet_router.post("/api/system/mode")
async def set_system_mode(req: SystemModeRequest):
    """Set global system operation mode (AUTO or MANUAL)."""
    try:
        new_mode = await system_mode_manager.set_mode(req.mode)
        return {
            "status": "SUCCESS",
            "mode": new_mode,
            "message": f"Hệ thống đã chuyển sang chế độ: {new_mode}",
        }
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@fleet_router.post("/api/system/start-auto")
async def system_auto_start(session: AsyncSession = Depends(get_session)):
    """System Auto Start Routine (Khởi Động Toàn Bộ Kho Trạm):
    1. Pre-flight Safety Diagnostic (Check E-Stop)
    2. PLC S7-1200: Enable START_PLC, ensure Lift Z-Axis is DOWN (Z_DOWN) (PLC handles Robot Home interlock)
    3. Set System Auto State -> RUNNING
    4. FIFO Queue: Auto dispatch first waiting mission
    """
    plc_mgr = PLCManager.get_instance()
    robot_mgr = RobotManager.get_instance()
    
    # 1. Safety check
    if plc_mgr.emergency_stop:
        raise HTTPException(
            status_code=400,
            detail="Không thể khởi động tự động! Hệ thống đang ở trạng thái Dừng Khẩn Cấp (E-STOP). Vui lòng Reset trước."
        )

    # Check staff operation interlock
    from app.services.staff_operation_manager import staff_operation_manager
    if staff_operation_manager.status == "RUNNING":
        raise HTTPException(
            status_code=409,
            detail="Không thể Khởi động Tự động Kho Trạm khi Nhân viên đang lấy hoặc thêm hàng! Vui lòng dừng hoặc chờ chu trình nhân viên hoàn tất."
        )

    await system_ws_manager.broadcast("SYSTEM_ALERT", {
        "level": "INFO",
        "message": "⚡ Đang kiểm tra an toàn và kích hoạt PLC S7-1200 (Homing Trục Z & Khởi Động Trạm)...",
    })

    # 2. PLC Enable & Homing: Chỉ cần gửi lệnh START_PLC đến PLC, chương trình PLC tự động thực hiện chu trình về Home khi bắt đầu
    try:
        await plc_mgr.execute_command(PLCCommand.START_PLC)
        plc_ok = True
    except Exception as err:
        logger.warning("PLC Start routine warning: %s", err)
        plc_ok = False

    robot_ok = robot_mgr.is_connected or robot_mgr.simulator_mode

    # 3. Set state to RUNNING
    await system_mode_manager.set_auto_running()

    # 4. FIFO Queue Dispatch
    mgr = MissionManager(session)
    dispatched = await mgr.auto_dispatch_next_mission()

    return {
        "status": "SUCCESS",
        "system_online": True,
        "mode": "AUTO",
        "auto_state": "RUNNING",
        "plc_status": "ONLINE" if plc_ok else "OFFLINE",
        "robot_status": "ONLINE" if robot_ok else "OFFLINE",
        "dispatched_mission_id": dispatched.id if dispatched else None,
        "message": f"🚀 Hệ thống kho trạm đã KHỞI ĐỘNG TỰ ĐỘNG! {'Đang chạy Mission #' + str(dispatched.id) if dispatched else 'Hàng chờ rỗng, sẵn sàng nhận đơn mới.'}",
    }


@fleet_router.post("/api/system/pause-auto")
async def system_auto_pause():
    """Pause AUTO system without switching to MANUAL mode."""
    await system_mode_manager.set_auto_paused()
    return {
        "status": "SUCCESS",
        "mode": "AUTO",
        "auto_state": "PAUSED",
        "is_scheduler_active": False,
        "message": "⏸️ Hệ thống kho trạm đã TẠM DỪNG TỰ ĐỘNG.",
    }


@fleet_router.post("/api/system/resume-queue")
async def system_resume_queue(session: AsyncSession = Depends(get_session)):
    """Resume FIFO Mission Queue auto-dispatch after operator has cleared/resolved an error."""
    if not system_mode_manager.is_auto():
        raise HTTPException(status_code=400, detail="Chỉ có thể tiếp tục hàng đợi khi hệ thống ở chế độ AUTO.")

    await system_mode_manager.set_auto_running()
    mgr = MissionManager(session)
    dispatched = await mgr.auto_dispatch_next_mission()
    return {
        "status": "SUCCESS",
        "resumed": True,
        "auto_state": "RUNNING",
        "dispatched_mission_id": dispatched.id if dispatched else None,
        "message": f"▶️ Đã tiếp tục xử lý hàng đợi FIFO! {'Đang chạy Mission #' + str(dispatched.id) if dispatched else 'Hàng chờ rỗng.'}",
    }


@fleet_router.post("/api/system/reset-tasks")
async def system_reset_tasks(session: AsyncSession = Depends(get_session)):
    """Reset all active/in-progress tasks:
    1. Reset Staff Operation (cancel outbound or stop inbound, status -> IDLE).
    2. Cancel all RUNNING/PAUSED missions in DB and linked delivery requests.
    3. Unlock station interlock (device_lock_manager.unlock_station()).
    4. Reset Station Service status to IDLE.
    5. Stop Camera if active.
    6. Set Auto state to STANDBY.
    7. Broadcast WebSocket updates for realtime UI sync.
    """
    from datetime import datetime
    from sqlalchemy import select
    from app.models.database import IntralogisticsMissionRecord, DeliveryRequestRecord
    from app.services.device_lock_manager import device_lock_manager
    from app.services.camera_manager import CameraManager
    from app.services.station_service import StationService
    from app.services.mission_queue_manager import MissionQueueManager
    from app.services.staff_operation_manager import staff_operation_manager

    now = datetime.utcnow()
    logger.info("🔄 [RESET_TASKS] Master Task Reset requested by Operator.")

    # 1. Reset Staff Operation
    staff_was_running = False
    try:
        if staff_operation_manager.status == "RUNNING" or staff_operation_manager._current_task:
            staff_was_running = True
            if staff_operation_manager._current_task and not staff_operation_manager._current_task.done():
                staff_operation_manager._current_task.cancel()
            if staff_operation_manager.active_type == "OUTBOUND":
                try:
                    await staff_operation_manager.cancel_outbound()
                except Exception:
                    pass
            elif staff_operation_manager.active_type == "INBOUND":
                try:
                    await staff_operation_manager.stop_inbound()
                except Exception:
                    pass
    except Exception as staff_err:
        logger.warning("Error resetting staff operation: %s", staff_err)
    finally:
        staff_operation_manager.status = "IDLE"
        staff_operation_manager.active_type = None
        staff_operation_manager.inbound_current_count = 0
        staff_operation_manager.inbound_target_count = 0
        staff_operation_manager.inbound_current_slot = None
        staff_operation_manager.outbound_queue.clear()
        staff_operation_manager.outbound_current_slot = None
        staff_operation_manager._stop_requested = False
        await staff_operation_manager.broadcast_status()

    # 2. Cancel all active RUNNING / PAUSED missions in Database
    stmt = select(IntralogisticsMissionRecord).where(
        IntralogisticsMissionRecord.status.in_(["RUNNING", "PAUSED"])
    )
    res = await session.execute(stmt)
    active_missions = list(res.scalars().all())
    cancelled_count = 0

    for mission in active_missions:
        mission.status = "CANCELLED"
        mission.state = "CANCELLED"
        mission.current_phase = "CANCELLED"
        mission.completed_at = now
        mission.step_details = f"🛑 Đã hủy bỏ nhiệm vụ do Người vận hành Reset lúc {now.strftime('%H:%M:%S')}."
        if mission.order_id:
            req = await session.get(DeliveryRequestRecord, mission.order_id)
            if req:
                req.status = "CANCELLED"
        cancelled_count += 1
        await system_ws_manager.broadcast("MISSION_FAILED", {
            "id": mission.id,
            "status": "CANCELLED",
            "reason": "OPERATOR_RESET",
        })

    if cancelled_count > 0:
        await session.commit()

    # 3. Reset Station Service & Device Lock
    station_svc = StationService.get_instance()
    station_svc.status = "IDLE"
    station_svc.current_operation = None
    station_svc.current_action = "READY"
    station_svc.message = "Đã Reset trạng thái trạm về Chờ (IDLE)"

    device_lock_manager.unlock_station()

    # 4. Stop Camera if running
    cam_mgr = CameraManager.get_instance()
    try:
        cam_mgr.stop_camera()
    except Exception:
        pass

    # 5. Set System Auto state to STANDBY
    await system_mode_manager.set_auto_standby()

    # 6. Broadcast all updates to WebSocket clients
    await system_ws_manager.broadcast("STATION_STATUS", station_svc.get_status().model_dump())
    await system_ws_manager.broadcast("SYSTEM_ALERT", {
        "level": "INFO",
        "message": f"🔄 Đã Reset hoàn tất: {cancelled_count} nhiệm vụ đã hủy, chế độ nhân viên và trạm đã về trạng thái Chờ (IDLE).",
    })

    q_mgr = MissionQueueManager(session)
    await q_mgr.broadcast_queue_state()

    return {
        "status": "SUCCESS",
        "cancelled_missions": cancelled_count,
        "staff_reset": staff_was_running,
        "auto_state": "STANDBY",
        "station_status": "IDLE",
        "message": f"🔄 Đã Reset thành công! {cancelled_count} nhiệm vụ bị hủy, đưa trạm và nhân viên về trạng thái Chờ (IDLE).",
    }

