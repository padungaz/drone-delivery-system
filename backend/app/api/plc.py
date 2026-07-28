from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.models.schemas import PLCCommand, PLCCommandRequest, PLCStatusResponse
from app.services.plc_manager import PLCManager
from app.websocket.manager import system_ws_manager

plc_router = APIRouter(prefix="/api/plc", tags=["PLC Docking Control"])


class PLCHatchRequest(BaseModel):
    action: str  # "OPEN" or "CLOSE"


class PLCLockRequest(BaseModel):
    action: str  # "LOCK" or "UNLOCK"


@plc_router.post("/command", response_model=PLCStatusResponse)
async def execute_plc_command(req: PLCCommandRequest):
    mgr = PLCManager.get_instance()
    status = await mgr.execute_command(req.command)

    # Broadcast PLC status to realtime WebSocket
    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return status


@plc_router.post("/hatch")
async def control_plc_hatch(req: PLCHatchRequest):
    mgr = PLCManager.get_instance()
    cmd = PLCCommand.Z_UP if req.action.upper() in ("OPEN", "Z_UP") else PLCCommand.Z_DOWN
    status = await mgr.execute_command(cmd)

    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return {
        "message": f"Lệnh {'Mở (Z_UP)' if cmd == PLCCommand.Z_UP else 'Đóng (Z_DOWN)'} nắp thành công!",
        "status": status.model_dump(),
    }


@plc_router.post("/lock")
async def control_plc_lock(req: PLCLockRequest):
    mgr = PLCManager.get_instance()
    cmd = PLCCommand.LOCK_DRONE if req.action.upper() in ("LOCK", "LOCK_DRONE") else PLCCommand.UNLOCK_DRONE
    status = await mgr.execute_command(cmd)

    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return {
        "message": f"Lệnh {'Khóa' if cmd == PLCCommand.LOCK_DRONE else 'Mở khóa'} Drone thành công!",
        "status": status.model_dump(),
    }


@plc_router.get("/status", response_model=PLCStatusResponse)
async def get_plc_status():
    mgr = PLCManager.get_instance()
    return mgr.get_status()
