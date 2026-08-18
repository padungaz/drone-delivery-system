from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.models.schemas import PLCCommand, PLCCommandRequest, PLCStatusResponse
from app.services.plc_manager import PLCManager
from app.services.device_lock_manager import device_lock_manager
from app.websocket.manager import system_ws_manager

plc_router = APIRouter(prefix="/api/plc", tags=["PLC Docking Control"])


class PLCHatchRequest(BaseModel):
    action: str  # "OPEN" or "CLOSE"


class PLCLockRequest(BaseModel):
    action: str  # "LOCK" or "UNLOCK"


@plc_router.post("/command", response_model=PLCStatusResponse)
async def execute_plc_command(req: PLCCommandRequest):
    # Safety Interlock: Block manual motion commands during AUTO mission, allow STOP/RESET
    if req.command not in (PLCCommand.STOP_PLC, PLCCommand.RESET_PLC) and device_lock_manager.is_device_locked("PLC01"):
        raise HTTPException(
            status_code=409,
            detail=f"PLC đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('PLC01')}! Vui lòng không can thiệp thủ công."
        )

    mgr = PLCManager.get_instance()
    status = await mgr.execute_command(req.command)

    # Broadcast PLC status to realtime WebSocket
    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return status


@plc_router.post("/hatch")
async def control_plc_hatch(req: PLCHatchRequest):
    if device_lock_manager.is_device_locked("PLC01"):
        raise HTTPException(
            status_code=409,
            detail=f"PLC đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('PLC01')}! Vui lòng không can thiệp thủ công."
        )

    mgr = PLCManager.get_instance()
    cmd = PLCCommand.Z_UP if req.action.upper() in ("OPEN", "Z_UP") else PLCCommand.Z_DOWN
    status = await mgr.execute_command(cmd)

    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return {
        "message": f"Lệnh {'Nâng Trục Z (Z_UP)' if cmd == PLCCommand.Z_UP else 'Hạ Trục Z (Z_DOWN)'} thành công!",
        "status": status.model_dump(),
    }


@plc_router.post("/lock")
async def control_plc_lock(req: PLCLockRequest):
    if device_lock_manager.is_device_locked("PLC01"):
        raise HTTPException(
            status_code=409,
            detail=f"PLC đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('PLC01')}! Vui lòng không can thiệp thủ công."
        )

    mgr = PLCManager.get_instance()
    cmd = PLCCommand.LOCK_DRONE if req.action.upper() in ("LOCK", "LOCK_DRONE") else PLCCommand.UNLOCK_DRONE
    status = await mgr.execute_command(cmd)

    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return {
        "message": f"Lệnh {'Khóa' if cmd == PLCCommand.LOCK_DRONE else 'Mở khóa'} Drone thành công!",
        "status": status.model_dump(),
    }


@plc_router.post("/start")
async def start_plc():
    if device_lock_manager.is_device_locked("PLC01"):
        raise HTTPException(
            status_code=409,
            detail=f"PLC đang bị khóa bởi Nhiệm vụ AUTO #{device_lock_manager.get_locking_mission_id('PLC01')}!"
        )
    mgr = PLCManager.get_instance()
    status = await mgr.execute_command(PLCCommand.START_PLC)
    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return {"message": "Lệnh Khởi động PLC (START_PLC) thành công!", "status": status.model_dump()}


@plc_router.post("/stop")
async def stop_plc():
    # Stop command is always allowed for emergency intervention
    mgr = PLCManager.get_instance()
    status = await mgr.execute_command(PLCCommand.STOP_PLC)
    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return {"message": "Lệnh Dừng PLC (STOP_PLC) thành công!", "status": status.model_dump()}


@plc_router.post("/reset")
async def reset_plc():
    # Reset command is always allowed
    mgr = PLCManager.get_instance()
    status = await mgr.execute_command(PLCCommand.RESET_PLC)
    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return {"message": "Lệnh Reset Lỗi PLC (RESET_PLC) thành công!", "status": status.model_dump()}


class PLCSensorRequest(BaseModel):
    detected: bool


@plc_router.post("/sensor/drone-detected")
async def set_simulated_drone_sensor(req: PLCSensorRequest):
    mgr = PLCManager.get_instance()
    mgr.set_drone_detected(req.detected)
    status = mgr.get_status()
    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return {
        "message": f"Cảm biến Drone Landing đã đặt thành: {'CÓ DRONE (DETECTED)' if req.detected else 'TRỐNG (NOT DETECTED)'}",
        "status": status.model_dump(),
    }


@plc_router.get("/status", response_model=PLCStatusResponse)
async def get_plc_status():
    mgr = PLCManager.get_instance()
    await mgr.read_plc_status()
    return mgr.get_status()
