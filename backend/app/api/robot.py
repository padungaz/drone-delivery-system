from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.models.schemas import RobotCommand, RobotCommandRequest, RobotStatusResponse
from app.services.robot_manager import RobotManager
from app.websocket.manager import system_ws_manager

robot_router = APIRouter(prefix="/api/robot", tags=["FAIRINO Robot Control"])


class RobotSlotRequest(BaseModel):
    slot: Optional[str] = None


@robot_router.post("/command", response_model=RobotStatusResponse)
async def execute_robot_command(req: RobotCommandRequest):
    mgr = RobotManager.get_instance()
    status = await mgr.execute_command(req.command, slot=req.slot)

    # Broadcast Robot status to realtime WebSocket
    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return status


@robot_router.post("/pick")
async def robot_pick(req: RobotSlotRequest):
    mgr = RobotManager.get_instance()
    status = await mgr.execute_command(RobotCommand.PICK, slot=req.slot)

    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return {
        "message": f"Lệnh Robot gắp hàng tại ô {req.slot or 'N/A'} thành công!",
        "status": status.model_dump(),
    }


@robot_router.post("/store")
async def robot_store(req: RobotSlotRequest):
    mgr = RobotManager.get_instance()
    status = await mgr.execute_command(RobotCommand.STORE, slot=req.slot)

    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return {
        "message": f"Lệnh Robot cất hàng vào ô {req.slot or 'N/A'} thành công!",
        "status": status.model_dump(),
    }


@robot_router.post("/home")
async def robot_home():
    mgr = RobotManager.get_instance()
    status = await mgr.execute_command(RobotCommand.MOVE_HOME)

    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return {
        "message": "Lệnh Robot di chuyển về HOME thành công!",
        "status": status.model_dump(),
    }


@robot_router.get("/status", response_model=RobotStatusResponse)
async def get_robot_status():
    mgr = RobotManager.get_instance()
    return mgr.get_status()
