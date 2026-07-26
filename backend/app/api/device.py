from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import get_session
from app.models.schemas import DeviceHeartbeatRequest, DeviceRegisterRequest, DeviceResponse
from app.services.device_manager import DeviceManager
from app.websocket.manager import system_ws_manager

device_router = APIRouter(prefix="/api/device", tags=["Device Management"])


@device_router.post("/register", response_model=DeviceResponse)
async def register_device(
    req: DeviceRegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    mgr = DeviceManager(session)
    device = await mgr.register_device(req)

    # Broadcast device status update to WebSocket clients
    await system_ws_manager.broadcast("DEVICE_STATUS", {
        "device_name": device.device_name,
        "type": device.device_type,
        "ip": device.ip_address,
        "status": device.status,
    })

    return device


@device_router.post("/heartbeat", response_model=DeviceResponse)
async def device_heartbeat(
    req: DeviceHeartbeatRequest,
    session: AsyncSession = Depends(get_session),
):
    mgr = DeviceManager(session)
    device = await mgr.update_heartbeat(req)
    if not device:
        return {"error": "Device not registered"}

    await system_ws_manager.broadcast("DEVICE_HEARTBEAT", {
        "device_name": device.device_name,
        "status": device.status,
        "last_heartbeat": device.last_heartbeat.isoformat(),
    })

    return device


@device_router.get("/list", response_model=List[DeviceResponse])
async def list_devices(
    session: AsyncSession = Depends(get_session),
):
    mgr = DeviceManager(session)
    return await mgr.get_all_devices()
