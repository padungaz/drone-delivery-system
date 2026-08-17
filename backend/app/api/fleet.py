from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import get_session
from app.services.fleet_manager import fleet_manager
from app.services.system_mode_manager import system_mode_manager
from app.services.mission_manager import MissionManager
from app.services.plc_manager import PLCManager
from app.services.robot_manager import RobotManager
from app.websocket.manager import system_ws_manager

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
    """System Auto Start Routine:
    1. Set mode to AUTO
    2. Health check PLC and Robot connections
    3. Broadcast SYSTEM_READY
    4. Scan FIFO Mission Queue and dispatch first waiting mission
    """
    await system_mode_manager.set_mode("AUTO")
    plc_mgr = PLCManager.get_instance()
    robot_mgr = RobotManager.get_instance()
    
    plc_ok = plc_mgr.is_connected or plc_mgr.simulator_mode
    robot_ok = robot_mgr.is_connected or robot_mgr.simulator_mode
    
    await system_ws_manager.broadcast("SYSTEM_ALERT", {
        "level": "INFO",
        "message": "⚡ Khởi động hệ thống tự động: Chế độ AUTO kích hoạt, kiểm tra kết nối thiết bị & Quét hàng chờ FIFO...",
    })
    
    mgr = MissionManager(session)
    dispatched = await mgr.auto_dispatch_next_mission()
    
    return {
        "status": "SUCCESS",
        "system_online": True,
        "mode": "AUTO",
        "plc_status": "ONLINE" if plc_ok else "OFFLINE",
        "robot_status": "ONLINE" if robot_ok else "OFFLINE",
        "dispatched_mission_id": dispatched.id if dispatched else None,
        "message": f"🚀 Hệ thống đã khởi động chế độ AUTO! {'Đang chạy Mission #' + str(dispatched.id) if dispatched else 'Hàng chờ rỗng, sẵn sàng nhận đơn mới.'}",
    }
