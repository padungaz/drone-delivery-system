from fastapi import APIRouter
from app.models.schemas import PLCCommandRequest, PLCStatusResponse
from app.services.plc_manager import PLCManager
from app.websocket.manager import system_ws_manager

plc_router = APIRouter(prefix="/api/plc", tags=["PLC Docking Control"])


@plc_router.post("/command", response_model=PLCStatusResponse)
async def execute_plc_command(req: PLCCommandRequest):
    mgr = PLCManager.get_instance()
    status = await mgr.execute_command(req.command)

    # Broadcast PLC status to realtime WebSocket
    await system_ws_manager.broadcast("PLC_STATUS", status.model_dump())
    return status


@plc_router.get("/status", response_model=PLCStatusResponse)
async def get_plc_status():
    mgr = PLCManager.get_instance()
    return mgr.get_status()
