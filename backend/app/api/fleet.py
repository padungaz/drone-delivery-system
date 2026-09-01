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

