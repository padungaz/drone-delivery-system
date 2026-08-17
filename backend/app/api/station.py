from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import get_session
from app.models.schemas import StationOperationResponse
from app.services.station_service import StationService

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
    station_svc = StationService(session)
    success = await station_svc.execute_load_product(req.target_slot, req.product_id, session)
    if not success:
        raise HTTPException(status_code=500, detail="Station LOAD_PRODUCT operation failed")
    return station_svc.get_status()


@station_router.post("/unload-product", response_model=StationOperationResponse)
async def trigger_unload_product(
    req: StationUnloadRequest,
    session: AsyncSession = Depends(get_session),
):
    station_svc = StationService(session)
    success = await station_svc.execute_unload_product(req.target_slot, req.product_id, session)
    if not success:
        raise HTTPException(status_code=500, detail="Station UNLOAD_PRODUCT operation failed")
    return station_svc.get_status()
