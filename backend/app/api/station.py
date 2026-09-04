from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import get_session
from app.models.schemas import StationOperationResponse
from app.services.station_service import StationService
from app.services.device_lock_manager import device_lock_manager
from app.services.staff_operation_manager import staff_operation_manager

station_router = APIRouter(prefix="/api/station", tags=["Docking Station Operation"])


class StationLoadRequest(BaseModel):
    target_slot: str = "A1"
    product_id: str = "SP001"


class StationUnloadRequest(BaseModel):
    target_slot: str = "A1"
    product_id: str = "SP001"


@station_router.get("/status", response_model=StationOperationResponse)
async def get_station_status():
    station_svc = StationService()
    return station_svc.get_status()


@station_router.post("/load-product", response_model=StationOperationResponse)
async def trigger_load_product(
    req: StationLoadRequest,
    session: AsyncSession = Depends(get_session),
):
    if device_lock_manager.is_station_busy():
        lock_desc = device_lock_manager.get_lock_description("STATION")
        raise HTTPException(
            status_code=409,
            detail=f"Trạm đang bận xử lý chu trình khác ({lock_desc})! Vui lòng không kích hoạt đồng thời.",
        )
    if staff_operation_manager.status == "RUNNING":
        raise HTTPException(
            status_code=409,
            detail="Chế độ nhân viên đang hoạt động, vui lòng dừng chế độ nhân viên trước khi thao tác trạm!",
        )

    device_lock_manager.lock_station(mission_id=0, reason="Thao tác nạp hàng trạm thủ công qua API")
    try:
        station_svc = StationService(session)
        success = await station_svc.execute_load_product(req.target_slot, req.product_id, session)
        if not success:
            raise HTTPException(status_code=500, detail="Station LOAD_PRODUCT operation failed")
        return station_svc.get_status()
    finally:
        device_lock_manager.unlock_station()


@station_router.post("/unload-product", response_model=StationOperationResponse)
async def trigger_unload_product(
    req: StationUnloadRequest,
    session: AsyncSession = Depends(get_session),
):
    if device_lock_manager.is_station_busy():
        lock_desc = device_lock_manager.get_lock_description("STATION")
        raise HTTPException(
            status_code=409,
            detail=f"Trạm đang bận xử lý chu trình khác ({lock_desc})! Vui lòng không kích hoạt đồng thời.",
        )
    if staff_operation_manager.status == "RUNNING":
        raise HTTPException(
            status_code=409,
            detail="Chế độ nhân viên đang hoạt động, vui lòng dừng chế độ nhân viên trước khi thao tác trạm!",
        )

    device_lock_manager.lock_station(mission_id=0, reason="Thao tác dỡ hàng trạm thủ công qua API")
    try:
        station_svc = StationService(session)
        success = await station_svc.execute_unload_product(req.target_slot, req.product_id, session)
        if not success:
            raise HTTPException(status_code=500, detail="Station UNLOAD_PRODUCT operation failed")
        return station_svc.get_status()
    finally:
        device_lock_manager.unlock_station()
