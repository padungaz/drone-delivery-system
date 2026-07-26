from fastapi import APIRouter
from app.models.schemas import RobotCommandRequest, RobotStatusResponse
from app.services.robot_manager import RobotManager
from app.websocket.manager import system_ws_manager

robot_router = APIRouter(prefix="/api/robot", tags=["FAIRINO Robot Control"])


@robot_router.post("/command", response_model=RobotStatusResponse)
async def execute_robot_command(req: RobotCommandRequest):
    mgr = RobotManager.get_instance()
    status = await mgr.execute_command(req.command, slot=req.slot)

    # Broadcast Robot status to realtime WebSocket
    await system_ws_manager.broadcast("ROBOT_STATUS", status.model_dump())
    return status


@robot_router.get("/status", response_model=RobotStatusResponse)
async def get_robot_status():
    mgr = RobotManager.get_instance()
    return mgr.get_status()
